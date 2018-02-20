#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import requests
import re
import json
import os
import zipfile

def initParser():
    parser = argparse.ArgumentParser(description='Create a backup of all your Sharelatex paper')
    parser.add_argument('-email', required=True, help='Sharelatex email')
    parser.add_argument('-password', required=True, help='Sharelatex password')
    parser.add_argument('-url', required=False, default="https://sharelatex.irisa.fr", help='The Sharelatex server')
    parser.add_argument('-output', default="~/sharelatex/backup", required=False, help='The ouput folder of the backup')
    parser.add_argument('-pdf', action="store_true", default=False, help='Download the PDF')
    return parser.parse_args()

rootUrl = "https://sharelatex.irisa.fr"
pathBackup = "~/sharelatex/backup"
isDownloadPDF = False
session = requests.Session()

def login(email, password):
    url = rootUrl + "/login"
    r = session.get(url, verify=False)
    m = re.search('window.csrfToken = "([^"]+)";', r.content)
    if m:
        csrf = m.group(1)
        data = {
            "email": email,
            "password": password,
            "redir": "/project",
            "_csrf": m.group(1)
        }
        r = session.post(url, data, verify=False)
        if r.status_code == 200:
            return 'message' not in r.json()
    return False

def getPapers():
    url = rootUrl + "/project"
    r = session.get(url, verify=False)
    m = re.search(" projects: ([^\n]+),\n", r.text.encode('utf-8'))
    if m:
        papers = json.loads(m.group(1))
        for paper in papers:
            if paper['archived']:
                papers.remove(paper)
        return papers 
    return []

def compile(paper):
    r = session.get(rootUrl + "/project/" + paper['id'], verify=False)
    m = re.search('window.csrfToken = "([^"]+)";', r.content)
    if m:
        csrf = m.group(1)

        url = rootUrl + "/project/" + paper['id'] + "/compile"
        data = {
            "rootDoc_id": paper['id'],
            "_csrf": csrf
        }
        r = session.post(url, data=data, verify=False, stream=True)
        return r.status_code == 200
    return False

def downloadPDF(paper):
    url = rootUrl + "/project/" + paper['id'] + "/output/output.pdf"
    r = session.get(url, verify=False, stream=True)
    if r.status_code != 200:
        return
    if not os.path.exists(pathBackup):
        os.makedirs(pathBackup)
    name = u'' + paper['name'].encode('ascii', 'ignore').replace("/", "-").replace(" ", "_").replace(".", "").replace(":", "")
    filename = os.path.join(pathBackup, name + '_' + paper['id'] + '.pdf'.strip())
    with open(filename, 'wb') as fd:
        for chunk in r.iter_content(100):
            fd.write(chunk)

def downloadZip(papers, oldPapers):
    for paper in sorted(papers):
        if paper in oldPapers:
            # the paper did not change
            continue
        url = rootUrl + "/project/" + paper['id'] + "/download/zip"
        r = session.get(url, verify=False, stream=True)
        if r.status_code != 200:
            continue
        if not os.path.exists(pathBackup):
            os.makedirs(pathBackup)
        if isDownloadPDF and compile(paper):
            downloadPDF(paper)
        name = u'' + paper['name'].encode('ascii', 'ignore').replace("/", "-").replace(" ", "_").replace(".", "").replace(":", "")
        print "\t%s" % name
        filename = os.path.join(pathBackup, paper['id'] + '.zip'.strip())
        with open(filename, 'wb') as fd:
            for chunk in r.iter_content(100):
                fd.write(chunk)
        with open(filename, 'rb') as fh:
            z = zipfile.ZipFile(fh)
            foldername = os.path.join(pathBackup, paper['id'].strip())
            if not os.path.exists(foldername):
                os.makedirs(foldername)
            for name in z.namelist():
                z.extract(name, foldername)
        os.remove(filename)

if __name__ == '__main__':
    args = initParser()
    rootUrl = args.url
    pathBackup = args.output
    isDownloadPDF = args.pdf

    pathBackup = os.path.expanduser(pathBackup)

    if login(args.email, args.password):
        papers = getPapers()

        oldPapers = []
        papersFilePath = os.path.join(pathBackup, "papers.json")
        if os.path.isfile(papersFilePath):
            with open(papersFilePath, "r") as fd:
                oldPapers = json.load(fd)
        with open(papersFilePath, "w") as fd:
            fd.write(json.dumps(papers, indent=2, sort_keys=True))
        print "Backup %d papers:" % (len(papers))
        downloadZip(papers, oldPapers)
    else:
        print "Invalid password"