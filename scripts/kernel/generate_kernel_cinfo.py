#! /usr/bin/env python2.7
# -*- mode: python; coding: utf-8; -*-
#
#  Codezero -- a microkernel for embedded systems.
#
#  Copyright © 2009  B Labs Ltd
#
import os, sys, shelve, glob
from os.path import join
from string import Template

PROJRELROOT = '../..'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), PROJRELROOT)))
sys.path.append(os.path.abspath("../"))

from scripts.config.projpaths import *
from scripts.config.configuration import *


cinfo_file_start = \
'''/*
 * Autogenerated container descriptions
 * defined for the current build.
 *
 * Copyright (C) 2009 Bahadir Balban
 */
#include <l4/generic/container.h>
#include <l4/generic/resource.h>
#include <l4/generic/capability.h>
#include <l4/generic/cap-types.h>
#include INC_PLAT(platform.h)
#include INC_PLAT(irq.h)

%s


__initdata struct container_info cinfo[] = {
'''
cinfo_file_end = \
'''
};
'''

cinfo_head_start = \
'''
\t[%d] = {
\t.name = "%s",
\t.npagers = 1,
\t.ncaps = %d,
\t.caps = {'''

cinfo_caps_end = \
'''
\t},
'''

cinfo_end = \
'''
\t\t},
\t},
'''

pager_start = \
'''
\t.pager = {
\t\t[0] = {
\t\t\t.start_address = (CONFIG_CONT%(cn)d_START_PC_ADDR),
\t\t\t.pager_lma = __pfn(CONFIG_CONT%(cn)d_PAGER_LOAD_ADDR),
\t\t\t.pager_vma = __pfn(CONFIG_CONT%(cn)d_PAGER_VIRT_ADDR),
\t\t\t.pager_size = __pfn(page_align_up(CONT%(cn)d_PAGER_MAPSIZE)),
\t\t\t.rw_pheader_start = %(rw_pheader_start)s,
\t\t\t.rw_pheader_end = %(rw_pheader_end)s,
\t\t\t.rx_pheader_start = %(rx_pheader_start)s,
\t\t\t.rx_pheader_end = %(rx_pheader_end)s,
\t\t\t.ncaps = %(caps)d,
\t\t\t.caps = {
'''
pager_end = \
'''
\t\t\t},
\t\t},
'''

# These are pager-only. If for container, remove the PAGER part, indent down some tabs.
cap_virtmem = \
'''
\t\t\t[%(capidx)d] = {
\t\t\t\t.target = %(cn)d,
\t\t\t\t.type = CAP_TYPE_MAP_VIRTMEM | CAP_RTYPE_CONTAINER,
\t\t\t\t.access = CAP_MAP_READ | CAP_MAP_WRITE | CAP_MAP_EXEC
\t\t\t\t\t| CAP_MAP_CACHED | CAP_MAP_UNCACHED | CAP_MAP_UNMAP | CAP_MAP_UTCB |
\t\t\t\t\tCAP_CACHE_INVALIDATE | CAP_CACHE_CLEAN,
\t\t\t\t.start = __pfn(CONFIG_CONT%(cn)d_PAGER_VIRT%(vn)d_START),
\t\t\t\t.end = __pfn(CONFIG_CONT%(cn)d_PAGER_VIRT%(vn)d_END),
\t\t\t\t.size = __pfn(CONFIG_CONT%(cn)d_PAGER_VIRT%(vn)d_END - CONFIG_CONT%(cn)d_PAGER_VIRT%(vn)d_START),
\t\t\t},
'''

cap_physmem = \
'''
\t\t\t[%(capidx)d] = {
\t\t\t\t.target = %(cn)d,
\t\t\t\t.type = CAP_TYPE_MAP_PHYSMEM | CAP_RTYPE_CONTAINER,
\t\t\t\t.access = CAP_MAP_READ | CAP_MAP_WRITE | CAP_MAP_EXEC |
\t\t\t\t\tCAP_MAP_CACHED | CAP_MAP_UNCACHED | CAP_MAP_UNMAP | CAP_MAP_UTCB,
\t\t\t\t.start = __pfn(CONFIG_CONT%(cn)d_PAGER_PHYS%(pn)d_START),
\t\t\t\t.end = __pfn(CONFIG_CONT%(cn)d_PAGER_PHYS%(pn)d_END),
\t\t\t\t.size = __pfn(CONFIG_CONT%(cn)d_PAGER_PHYS%(pn)d_END - CONFIG_CONT%(cn)d_PAGER_PHYS%(pn)d_START),
\t\t\t},
'''


pager_ifdefs_todotext = \
'''
/*
 * TODO:
 * This had to be defined this way because in CML2 there
 * is no straightforward way to derive symbols from expressions, even
 * if it is stated in the manual that it can be done.
 * As a workaround, a ternary expression of (? : ) was tried but this
 * complains that type deduction could not be done.
 */'''

# This will be filled after the containers are compiled
# and pager binaries are formed
pager_mapsize = \
'''
#define CONT%d_PAGER_SIZE     %s
'''

pager_ifdefs = \
'''
#if defined(CONFIG_CONT%(cn)d_TYPE_LINUX)
    #define CONT%(cn)d_PAGER_MAPSIZE \\
                (CONT%(cn)d_PAGER_SIZE + CONFIG_CONT%(cn)d_LINUX_ZRELADDR - \\
                 CONFIG_CONT%(cn)d_LINUX_PHYS_OFFSET)
#else
    #define CONT%(cn)d_PAGER_MAPSIZE (CONT%(cn)d_PAGER_SIZE)
#endif
'''

def generate_pager_memory_ifdefs(config, containers):
    pager_ifdef_string = ""
    linux = 0
    for c in containers:
        if c.type == "linux":
            if linux == 0:
                pager_ifdef_string += pager_ifdefs_todotext
                linux = 1
        pager_ifdef_string += \
            pager_mapsize % (c.id, c.pager_size)
        pager_ifdef_string += pager_ifdefs % { 'cn' : c.id }
    return pager_ifdef_string

def generate_kernel_cinfo(cinfo_path):
    config = configuration_retrieve()
    containers = config.containers
    containers.sort()

    print "Generating kernel cinfo..."
    #config.config_print()

    pager_ifdefs = generate_pager_memory_ifdefs(config, containers)

    with open(str(cinfo_path), 'w+') as cinfo_file:
        fbody = cinfo_file_start % pager_ifdefs
        for c in containers:
	    for caplist in [c.caplist["CONTAINER"], c.caplist["PAGER"]]:
            	total_caps = caplist.virt_regions + caplist.phys_regions + len(caplist.caps)
		if caplist == c.caplist["CONTAINER"]:
	            fbody += cinfo_head_start % (c.id, c.name, total_caps)
	        else:
                    fbody += pager_start % { 'cn' : c.id, 'caps' : total_caps,
                                         'rw_pheader_start' : hex(c.pager_rw_pheader_start),
                                         'rw_pheader_end' : hex(c.pager_rw_pheader_end),
                                         'rx_pheader_start' : hex(c.pager_rx_pheader_start),
                                         'rx_pheader_end' : hex(c.pager_rx_pheader_end),
                                       }
            	cap_index = 0
            	for mem_index in range(caplist.virt_regions):
                    fbody += cap_virtmem % { 'capidx' : cap_index, 'cn' : c.id, 'vn' : mem_index }
                    cap_index += 1
            	for mem_index in range(caplist.phys_regions):
                    fbody += cap_physmem % { 'capidx' : cap_index, 'cn' : c.id, 'pn' : mem_index }
                    cap_index += 1

            	for capkey, capstr in caplist.caps.items():
                    templ = Template(capstr)
                    fbody += templ.safe_substitute(idx = cap_index)
                    cap_index += 1

		if caplist == c.caplist["CONTAINER"]:
                    fbody += cinfo_caps_end
		else:
                    fbody += pager_end
                    fbody += cinfo_end
        fbody += cinfo_file_end
        cinfo_file.write(fbody)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        generate_kernel_cinfo(join(PROJROOT, sys.argv[1]))
    else:
        generate_kernel_cinfo(KERNEL_CINFO_PATH)
