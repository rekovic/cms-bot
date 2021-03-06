#!/usr/bin/env python
"""
This job will check if there are queued jobs for jenkins slaves with 'condor' label and how many.
Then it will kill needed amount of placeholder jobs.
"""
from __future__ import print_function
from pprint import pprint
import re
from xml.etree import cElementTree as ET
import requests
from collections import defaultdict
from os import environ

RX_Project = re.compile('.+\/job\/(.+)\/(\d+)\/')
RX_Queue_why = re.compile(u'^Waiting for next available executor.*\u2018(.*)\u2019')
JENKINS_URL = environ['LOCAL_JENKINS_URL']
WORKSPACE = environ['WORKSPACE']
running_job_xml = JENKINS_URL + '/api/xml?&tree=jobs[builds[url,building]]&xpath=/hudson/job/build[building="true"]&wrapper=jobs'
job_que_json = JENKINS_URL + '/queue/api/json?tree=items[url,why]'


def etree_to_dict(t):
    d = {t.tag: {} if t.attrib else None}
    children = list(t)
    if children:
        dd = defaultdict(list)
        for dc in map(etree_to_dict, children):
            for k, v in dc.items():
                dd[k].append(v)
        d = {t.tag: {k: v[0] if len(v) == 1 else v
                     for k, v in dd.items()}}
    if t.attrib:
        d[t.tag].update(('@' + k, v)
                        for k, v in t.attrib.items())
    if t.text:
        text = t.text.strip()
        if children or t.attrib:
            if text:
                d[t.tag]['#text'] = text
        else:
            d[t.tag] = text
    return d


def main():
    r_xml = requests.get(running_job_xml)
    r_json = requests.get(job_que_json)
    que_to_free = 0

    # get jobs that are waiting for a specific executor
    print("Queued jobs:", job_que_json)
    pprint(r_json.json())
    print("----")
    que_job_list = r_json.json()['items']
    for j in que_job_list:
        m = RX_Queue_why.match(j['why'])
        if m:
            print((m.groups()))
            label = m.group(0)
            if 'condor' in label:
                que_to_free += 1
    print("Number jobs needed to free")
    pprint(que_to_free)
    print("----\n")

    # get running placeholder job
    xml = ET.XML(r_xml.text)
    parsed_dict = etree_to_dict(xml)
    print("Running jobs", running_job_xml )
    pprint(parsed_dict)
    jobs_to_kill = []
    for el in parsed_dict['jobs']['build']:
        match = RX_Project.match(el['url'])
        project = match.group(1)
        j_number = match.group(2)
        if 'grid-keep-node-busy' != project:
            continue
        jobs_to_kill.append([project, j_number])
    print("Jobs to kill:")
    pprint(jobs_to_kill)
    print("size:" + str(len(jobs_to_kill)))

    # create property file for each job to be killed
    for i in range(0, min(que_to_free, len(jobs_to_kill))):
        with open("{0}/job-to-kill-{1}.txt".format(WORKSPACE, i), 'w') as f:
            f.write("JENKINS_PROJECT_TO_KILL={0}\nBUILD_NR={1}\n".format(*jobs_to_kill[i]))


if __name__ == '__main__':
    main()
