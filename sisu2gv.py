#!/usr/bin/env python
"""
Usage: sisu2gv.py -h

The script can generate Graphviz (https://graphviz.org/) files from Tampere
University Sisu curricula database to visualize any degree programme.
It works by reading the data using the Sisu API and writes a gv file that 
can then be drawn to a graph visualization using Graphviz dot command.
"""

__author__ = "Jussi Rasku"
__copyright__ = "Copyright 2022, Jussi Rasku"
__license__ = "MIT"

import requests
import json
import logging
import textwrap

from pprint import pprint
from os import path
from datetime import date

# Global datastructure to store and map course id/code to course data
cid2c = {}
# Global datastructure to store prerequisites for processing
queued_prerequisites = []
cache_dir = "./cache/"

SISU_PROG_URL = 'https://sis-tuni.funidata.fi/kori/api/modules/'
SISU_GROUP_URL = 'https://sis-tuni.funidata.fi/kori/api/modules/by-group-id'
SISU_COURSE_URL = 'https://sis-tuni.funidata.fi/kori/api/course-units/by-group-id'

def get_cached(id):
    full_path = path.join(cache_dir, id+'.json')
    if path.exists(full_path):
        with open(full_path, 'r', encoding='utf-8') as rf:
            return json.load(rf)
    return None

def store_to_cache(this_data, with_id):
    full_path = path.join(cache_dir, with_id+'.json')
    with open(full_path, "w", encoding='utf-8') as wf:
        jsonstr = json.dumps(this_data, indent=2)
        wf.write(jsonstr)

def queue_validate_and_clean_preprequisites(reqs):
    global queued_prerequisites
    queued_prerequisites.append( reqs )

def validate_and_clean_queued_preprequisites(curriculum):
    global queued_prerequisites
    for reqs in queued_prerequisites:
        to_rm = []
        for rq in reqs:
            if parse_course(rq, curriculum, in_main_tree=False) is None:
                to_rm.append(rq)
        for rmid in to_rm:
            reqs.remove(rmid)

def parse_course(cid, curriculum, in_main_tree=True):
    global cid2c

    c_data = get_cached(cid)
    if not c_data:
        params = {
            'groupId':cid,
            'universityId':'tuni-university-root-id'
        }
        resp = requests.get(url=SISU_COURSE_URL, params=params)
        logging.info("Hit SISU endpoint :"+resp.url)
        if (resp.status_code!=200):
            logging.warning(f"Got HTTP status code {resp.status_code} when getting course with ID {cid}, skipping it.")
            return None
        
        c_data = resp.json()
        store_to_cache(c_data, cid)
    
    for c in c_data:
        valid_for_curriculums = c['curriculumPeriodIds'] 
        # can be empty? assume it is valid if no years is set
        if valid_for_curriculums and not curriculum in valid_for_curriculums:
            continue

        code = c['code']
        if 'fi' in c['name']:
            name = c['name']['fi']
        else:
            name = c['name']['en']

        rprqs = []
        for prs in c['recommendedFormalPrerequisites']:
            for pr in prs['prerequisites']:
                if pr['type']!='CourseUnit':
                    logging.warning("Skipping non-course prerequisite")
                    continue
                if pr['courseUnitGroupId'] not in rprqs:
                    rprqs.append(pr['courseUnitGroupId'])

        cprqs = []
        for prs in c['compulsoryFormalPrerequisites']:
            for pr in prs['prerequisites']:
                if pr['type']!='CourseUnit':
                    logging.warning("Skipping non-course prerequisite")
                    continue
                if pr['courseUnitGroupId'] not in rprqs:
                    cprqs.append(pr['courseUnitGroupId'])

        course = {'code':code, 'name':name, 'rec_prqs':rprqs, 'com_prqs':cprqs}

        course['key'] = c['code'].replace(".", "_")
        # Sometimes the course may be in alternative module groups. Create a new key!
        #  TODO: What if it is in 3 groups?
        if in_main_tree and cid in cid2c:
            course['key']+="_alt"
        cid2c[cid] = course
        return course
    return None

def parse_module_group(gid, curriculum):
    """ Parses module group type data in the Sisu data. """
    sm_data = get_cached(gid)
    if not sm_data:
        params = {
            'groupId':gid,
            'universityId':'tuni-university-root-id'
        }
        resp = requests.get(url=SISU_GROUP_URL, params=params)
        logging.info("Hit SISU endpoint :"+resp.url)
        if (resp.status_code!=200):
            logging.warning(f"Got HTTP status code {resp.status_code} when getting degree module ID {gid}, skipping it.")
            return None

        sm_data = resp.json()
        store_to_cache(sm_data, gid)
    
    for alt_grouping in sm_data:
        valid_for_curriculums = alt_grouping['curriculumPeriodIds'] 
        # can be empty? assume it is valid if no years is set
        if valid_for_curriculums and not curriculum in valid_for_curriculums:
            continue

        name = alt_grouping['name']['fi']
        type = alt_grouping['type']
        
        node = {'name':name, 'type':type, 'children':[]}
        node['children'] = parse_rules(alt_grouping['rule'], curriculum)
        if not node['children']: 
            continue
        return node
    return None

def parse_rules(rd, curriculum):
    """ Recursively parses rules, modules, and courses in the Sisu data. """
    type = rd['type']
    if type=='CreditsRule': 
        # ignore credits info for now, just recurese into child
        return parse_rules(rd['rule'], curriculum)
    elif type=='CompositeRule':
        children = []
        for rule in rd['rules']:
            if 'moduleGroupId' in rule:
                gid = rule['moduleGroupId']
                gmg = parse_module_group(gid, curriculum)
                if gmg:
                    children.append(gmg)
            elif 'courseUnitGroupId' in rule:
                cid = rule['courseUnitGroupId']
                course = parse_course(cid, curriculum)
                if course is not None:
                    queue_validate_and_clean_preprequisites(course['rec_prqs'])
                    queue_validate_and_clean_preprequisites(course['com_prqs'])
                    children.append(course)
            else:
                name = ''
                type = 'grouping'
                if 'description' in rule and rule['description']:
                    name = rule['description']['fi'].strip().strip("<p>").strip("</p>")
                elif 'allMandatory' in rule and rule['allMandatory']:
                    name = 'Pakolliset'

                node = {'name':name, 'type':type, 'children':[]}
                node['children'] = parse_rules(rule, curriculum)
                if node['children']:
                    children.append(node)
        if not children:
            return None
        return children
    elif type=='CourseUnitRule':
        cid = rule['courseUnitGroupId']
        course = parse_course(cid, curriculum)
        if course is None:
            return None
        queue_validate_and_clean_preprequisites(course['rec_prqs'])
        queue_validate_and_clean_preprequisites(course['com_prqs'])
        return course 
    else:
        print("WARNING: unknown type ", type)
    return None

def compress(hierarchy):
    """ Compresses the module/course hierachy by removing useless (for the
    graph!) information such as groupings etc."""
    replacements = []
    for g in hierarchy:
        if 'children' in g and len(g['children'])==1:
            only_child = g['children'][0]
            if 'children' in only_child:
                #only_child['name'] = g['name']+"/"+only_child['name']
                replacements.append( (g, only_child) )
    for this, that in replacements:
        ti = hierarchy.index(this)
        hierarchy[ti]=that

def draw_graph_for_degree_programme(
  pgid, curriculum, 
  output_gv_file_path=None,
  also_recommended=True,
  course_blacklist=[],
  extra_data={}):

    """Fetch data from Sisu (or from cache) produce a graphviz file to
    illustrate the structure, courses and course prerequisites. 

    Disclaimer: The representation is not necessarily entirely truthful.
    a) because all the data in Sisu is not in sctructural format (some of it 
      is is given as freeform text).
    b) there might be (or, surely is!) special cases not handled by this
      visualizer.

    :param str gpid: The degree program id as an otm code.
    :param str curriculum: The curriculum code to use (e.g. "uta-lvv-2022").
    :param str output_gv_file_path: The file name to produce the graphviz graph definition.
    :param bool also_recommended: Also draw recommended courses.
    :param list course_blacklist: list of course codes/labels not to add to the graph.
    :param dict extra_data: Extra data such as course icons and manual prerequisites. Read the code.
     """

    global cid2c

    if course_blacklist:
        course_blacklist = [cc.replace(".","_") for cc in course_blacklist]

    p_data = get_cached(pgid)
    if not p_data:
        resp = requests.get(url=SISU_PROG_URL+pgid)
        logging.info("Hit SISU endpoint :"+resp.url)
        if (resp.status_code!=200):
            logging.warning(f"Got HTTP status code {resp.status_code} when getting degree programme ID {pgid}, skipping it.")
            return None

        p_data = resp.json()
        store_to_cache(p_data, pgid)

    module_hierarchy = []
    # TODO: make this more robust and smart as this probably assumes too much
    #  of the degree program structure of the rules.
    for submodule in p_data['rule']['rules'][0]['rules']:
        gid = submodule['moduleGroupId']
        smg =  parse_module_group(gid, curriculum)
        if smg:
            module_hierarchy.append(smg)
    # Process the prerequisites now that we know all the ids
    validate_and_clean_queued_preprequisites(curriculum)

    # This removes/shrinks/combines unnecessary rules for visualization such as
    #  credit rules, groupings etc.
    compress(module_hierarchy)
    
    if __debug__:
        pprint(module_hierarchy)

    if output_gv_file_path is None:
        output_gv_file_path = pgid+".gv"
        
    with open(output_gv_file_path, 'w', encoding="utf-8") as wf:
        wf.write("digraph G {\n")
        wf.write("rankdir=\"LR\";\n")
        
        sgidx = 1
        indent = 0

        in_clusters = []
        all_com_prqs = []
        all_rec_prqs = []

        def write_course(c):
            # Closure for these
            nonlocal indent, all_com_prqs, all_rec_prqs

            ck1 = c['key']
            cc1 = c['code']
            wrapname = textwrap.fill(c['name'], 20, max_lines=3, placeholder="...").replace('\n',r'<BR/>')
            icon =  ' '+extra_data['course_icons'][ck1] if extra_data and ck1 in extra_data['course_icons'] else ''
            #wf.write(indent*"  "+f"{ck1} [shape=record, label=\"{c['code']} {icon}|{wrapname}\"];\n")
            wf.write(indent*"  "+f"{ck1} [shape=plaintext, label=<\n"+
            
            (indent+1)*"  "+""" <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">\n"""+ 
            (indent+2)*"  "+f"<TR><TD>{cc1+icon}</TD></TR>\n"+
            (indent+2)*"  "+f"<TR><TD>{wrapname}</TD></TR>\n"+
            (indent+1)*"  "+"</TABLE> > ];\n")

            for pr in c['com_prqs']:
                if pr in cid2c:
                    c2 = cid2c[pr]
                    ck2 = c2['key']
                    all_com_prqs.append((ck2, ck1))
            for pr in c['rec_prqs']:
                if pr in cid2c:
                    c2 = cid2c[pr]
                    ck2 = c2['key']
                    all_rec_prqs.append((ck2, ck1))
        
        def write_cluster(sg, blacklist):
            # Closure for these
            nonlocal sgidx, indent, in_clusters
            
            wf.write(indent*"  "+"subgraph cluster_%d {\n"%sgidx)
            sgidx+=1
            indent+=1
            wf.write(indent*"  "+"label = \"%s\";\n"%sg['name'])
            
            for c in sg['children']:
                if 'children' in c:
                    write_cluster(c, blacklist)
                else:
                    if c['key'] in blacklist:
                        continue
                    write_course(c)
                    in_clusters.append(c['key'])

            indent-=1
            wf.write(indent*"  "+"}\n")
        
        def write_prerequisites(prqs, blacklist, style=""):
            for from_c, to_c in prqs:
                if from_c in blacklist or to_c in blacklist: continue

                if style:
                    wf.write(indent*"  "+f"{from_c}->{to_c} [style=\"{style}\"];\n")
                else:
                    wf.write(indent*"  "+f"{from_c}->{to_c};\n")


        for sg in module_hierarchy:
            write_cluster(sg, course_blacklist)

        active_prqs = []
        write_prerequisites(all_com_prqs, course_blacklist, style="")
        active_prqs+=[prq for prq, c in all_com_prqs]
        if also_recommended:
            write_prerequisites(all_rec_prqs, course_blacklist, style="dashed")
            active_prqs+=[prq for prq, c in all_rec_prqs]
        if extra_data and extra_data['manual_prerequisites']:
            # it is a list of dicts
            man_prqs = []
            for d in extra_data['manual_prerequisites']:
                man_prqs+=list(d.items())
            write_prerequisites(man_prqs, course_blacklist, style="dotted")
            active_prqs+=[prq for prq, c in man_prqs]

        loose_courses = []
        wf.write("{ rank=source; ")
        for c in cid2c.values():
            cc = c['code']
            ck = c['key']

            # Might already have a node,
            # might be blacklisted
            # might not be added
            if cc in in_clusters or \
               ck in course_blacklist or \
               ck not in active_prqs:
                continue

            wf.write(f"{ck}; ")
            loose_courses.append(c)
        wf.write("}\n")

        for c in loose_courses:
            write_course(c)

        wf.write("}\n")


if __name__=="__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("degree_programme", type=str,
                        help="the Sisu otm id for the degree program to visualize")
    parser.add_argument("-o", "--outputfile", default=None,
                        help="write to this file (by default the name is determined by the otm id)")
    parser.add_argument("-y", "--year", default=date.today().year, type=int,
                        help="override the curriculum year")
    parser.add_argument("-c", "--cachedir", default=None,
                        help="override the default cache directory for the Sisu data")
    parser.add_argument("-b", "--blacklist", action="append", help="Blacklist "+
      "these course codes from the graph. The parameter can be give multiple "+
      "times to blacklist multiple courses")
    parser.add_argument("-a", "--also_recommended", action='store_true', help = "Also show recommended course prerequisites.")
    parser.add_argument("-e", "--extradata", default=None,
                        help=".json file with some additional data (see readme)")
    parser.add_argument("-v", "--verbose", dest="verbosity", action="count", default=0,
                    help="Set verbosity level (default shows warnings, show also info = -v, also debug = -vv")
    
    args = parser.parse_args()
    
    log_levels = {
        0: logging.WARN,
        1: logging.INFO,
        2: logging.DEBUG,
    }
    logging.basicConfig(level=log_levels[min(args.verbosity,max(log_levels.keys()))])
    
    if args.cachedir:
        cache_dir = args.cachedir

    extra_data = {}
    if args.extradata:
        with open(args.extradata, 'r', encoding='utf-8') as rf:
            extra_data = json.load(rf)
    
    curriculum = "uta-lvv-%d"%args.year
    
    draw_graph_for_degree_programme(
        args.degree_programme,
        curriculum,
        args.outputfile,
        args.also_recommended,
        args.blacklist,
        extra_data
    )