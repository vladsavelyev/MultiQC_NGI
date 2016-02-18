#!/usr/bin/env python
""" MultiQC hook functions - we tie into the MultiQC
core here to add in extra functionality. """

from __future__ import print_function
from collections import OrderedDict
from couchdb import Server
import logging
import os
import re
import yaml

import multiqc
from multiqc.utils import (report, config)

log = logging.getLogger('multiqc')

report.ngi = dict()

class ngi_metadata():
  def __init__(self):
    self.couch = self.connect_statusdb()
    self.find_ngi_project()

  def find_ngi_project(self):
    """ Try to find a NGI project ID in the sample names.
    If just one found, add to the report header. """
    
    # Collect sample IDs
    # Want to run  before the general stats table is built
    s_names = [x for m in report.general_stats for x in report.general_stats[m]['data']]
    project_ids = set()
    for s_name in s_names:
      m = re.search(r'(P\d{3,5})', s_name)
      if m:
        project_ids.add(m.group(1))
    project_ids = list(project_ids)
    if len(project_ids) == 1:
      log.info("Found one NGI project id: {}".format(project_ids[0]))
      self.add_project_header(project_ids[0])
    elif len(project_ids) > 1:
      log.warn("Multiple NGI project IDs found! {}".format(",".join(project_ids)))
    else:
      log.info("No NGI project IDs found.")


  def add_project_header(self, pid):
    """ Add NGI project information to report header """
    self.get_ngi_project_metadata(pid)
    self.general_stats_sample_meta(pid)


  def get_ngi_project_metadata(self, pid):
    """ Get project metadata from statusdb """
    if self.couch is None:
      return None
    p_view = self.couch['projects'].view('project/summary')
    p_summary = None
    for row in p_view:
      if row['key'][1] == pid:
        p_summary = row
    
    try:
      p_summary = p_summary['value']
    except TypeError:
      log.error("statusdb returned no rows when querying {}".format(pid))
      return None
    
    log.info("Found metadata for NGI project '{}'".format(p_summary['project_name']))
    
    config.title = '{}: {}'.format(pid, p_summary['project_name'])
    config.project_name = p_summary['project_name']
    report.ngi['pid'] = pid
    keys = {
      'contact_email':'contact',
      'application': 'application'
    }
    d_keys = {
      'customer_project_reference': 'customer_project_reference',
      'project_type': 'type',
      'sequencing_platform': 'sequencing_platform',
      'sequencing_setup': 'sequencing_setup'
    }
    for i, j in keys.items():
      try:
        report.ngi[i] = p_summary[j]
      except KeyError:
        raise
    for i, j in d_keys.items():
      try:
        report.ngi[i] = p_summary['details'][j]
      except KeyError:
        raise

    # import json
    # print(json.dumps(p_summary, indent=4))

  def general_stats_sample_meta(self, pid):
      meta = self.get_ngi_samples_metadata(pid)
      if meta is not None:
        report.write_data_file(meta, 'ngi_meta')
      
      # if len(meta) > 0:
      #   headers = OrderedDict()
      #   headers['reads_aligned_percentage'] = {
      #     'title': '% Aligned',
      #     'description': '% reads with at least one reported alignment',
      #     'max': 100,
      #     'min': 0,
      #     'scale': 'YlGn',
      #     'format': '{:.1f}%'
      #   }
      #   headers['reads_aligned'] = {
      #     'title': 'M Aligned',
      #     'description': 'reads with at least one reported alignment (millions)',
      #     'min': 0,
      #     'scale': 'PuRd',
      #     'modify': lambda x: x / 1000000,
      #     'shared_key': 'read_count'
      #   }
      #   multiqc.modules.BaseMultiqcModule.general_stats_addcols(meta) #, headers)


  def get_ngi_samples_metadata(self, pid):
    """ Get project sample metadata from statusdb """
    if self.couch is None:
      return None
    p_view = self.couch['projects'].view('project/samples')
    p_samples = p_view[pid]
    if not len(p_samples.rows) == 1:
      log.error("statusdb returned {} rows when querying {}".format(len(p_samples.rows), pid))
      return None
    return p_samples.rows[0]['value']


  def connect_statusdb(self):
    """ Connect to statusdb """
    try:
      conf_file = os.path.join(os.environ.get('HOME'), '.ngi_config', 'statusdb.yaml')
      with open(conf_file, "r") as f:
        config = yaml.load(f)
    except IOError:
      log.warn("Could not open the MultiQC_NGI statusdb config file {}".format(conf_file))
      return None
    try:
      couch_user = config['statusdb']['username']
      password = config['statusdb']['password']
      couch_url = config['statusdb']['url']
      port = config['statusdb']['port']
    except KeyError:
      log.error("Error parsing the config file {}".format(conf_file))
      return None
    return Server("http://{}:{}@{}:{}".format(couch_user, password, couch_url, port))


  
