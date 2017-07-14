
from warnings import warn
import re, copy

from model import Species, Reaction

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

def tagmatch(elem,tag):
    return elem.tag.endswith('}' + tag)

def findfirst(elem,tag):
    for e in elem.getiterator():
        if tagmatch(e,tag):
            return e

def findall(elem,tag):
    return [e for e in elem.getiterator() if tagmatch(e,tag)]

def parse_sbml_file(file, subsystem_pattern='SUBSYSTEM: *(?P<value>.*\S+.*) *\</',
                    gpr_pattern='GENE_ASSOCIATION: *(?P<value>.*\S+.*) *\</',
                    gene_split_pattern=' or | and |[() ]'):
    # returns a dict:
    #   species:  { 'id' : Species(...) }
    #   reactions:  { 'id' : Reaction(...) }
    #   compartments { 'id' : ('name','outside') }

    tree = ET.ElementTree(file=file)
    model = tree.getroot()[0]

    listOfCompartments = findfirst(model,'listOfCompartments')
    listOfSpecies = findfirst(model,'listOfSpecies')
    listOfReactions = findfirst(model,'listOfReactions')

    compartments = {}
    for elem in findall(listOfCompartments,'compartment'):
        compartments[elem.get('id')] = (elem.get('name'),elem.get('outside'))

    def parse_species(sp):
        return Species(sp.get('id'),
                       name=sp.get('name'),
                       compartment=sp.get('compartment'))

    species = {}
    for sp in findall(listOfSpecies,'species'):
        parsed = parse_species(sp)
        species[parsed.id] = parsed

    def parse_reaction(rxn):
        rid = rxn.get('id')
        name = rxn.get('name')
        reversible = rxn.get('reversible') == "true"

        reactants = findfirst(rxn,'listOfReactants')
        products = findfirst(rxn,'listOfProducts')
        def parse_speciesrefs(listof):
            parsed = [ref.get('species')
                      for ref in findall(listof,'speciesReference')]
            if parsed:
                final = []
                for x in parsed:
                    if x not in species:
                        warning = 'Reaction {0} species {1} not found.'
                        warn(warning.format(rid,x))
                    else:
                        final.append(copy.deepcopy(species[x]))
            return final
        if reactants:
            reactants = parse_speciesrefs(reactants)
        if products:
            products = parse_speciesrefs(products)

        # parse the subsystem, if available
        notes = findfirst(rxn,'notes')
        if notes == None: notetext = ""
        else: notetext = ET.tostring(notes)
        def parse_notes(pattern):
            patt = re.compile(pattern)
            results = patt.search(notetext)
            if results:
                return results.group("value")
            else:
                return None

        subsystem = parse_notes(subsystem_pattern)

        # check SBML level for parsing GPR
        sbml_level = tree.getroot().attrib['level']
        # recursive helper function for parsing genes from SBML level 3 files and generating a GPR string
        def get_genes(node,bool_op=""):
            ids = []
            for child in node:
                if child.tag.endswith('geneProductRef'):
                    for id_tag in child.attrib:
                        if id_tag.endswith("geneProduct"):
                            gene_id = child.attrib[id_tag]
                            if gene_id[:2] == "G_":
                                gene_id = gene_id[2:]
                                ids.append(gene_id)
                elif child.tag.endswith("or"):
                    or_group = "(" + get_genes(child," or ") + ")"
                    ids.append(or_group)
                elif child.tag.endswith("and"):
                    and_group = "(" + get_genes(child," and ") + ")"
            gpr_string = ""
            while ids:
                gpr_string += ids.pop(0)
                if ids:
                    gpr_string += bool_op
            return gpr_string

        if sbml_level == "2":
            gpr = parse_notes(gpr_pattern)
            if gpr:
                genes = set([x for x in re.split(gene_split_pattern,gpr) if x])
            else:
                genes = None

        # parsing genes from sbml level 3
        else:
            gpa = findfirst(rxn,'geneProductAssociation')
            gpr = ""
            genelist = []
            if gpa:
                gpr = get_genes(gpa)
                genelist = re.split(gene_split_pattern,gpr)
            if genelist:
                genes = set(genelist)
            else:
                genes = None
                gpr = None
            print(genes)
        return Reaction(rid,
                        name=name,
                        reversible=reversible,
                        reactants=reactants,
                        products=products,
                        subsystem=subsystem,
                        gpr=gpr,
                        genes=genes)

    reactions = {}
    for rxn in findall(listOfReactions,'reaction'):
        parsed = parse_reaction(rxn)
        reactions[parsed.id] = parsed

    return dict(species=species, reactions=reactions, compartments=compartments)


if __name__ == '__main__':
    species,reactions,compartments = parse_sbml_file(file="../test/ecoli2011.xml")

    print ("found", len(species), "species")
    print ("found", len(reactions), "reactions")
    print ("found", len(compartments), "compartments")

    print (compartments)
