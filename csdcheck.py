#####################################################################
# File: csdcheck.py
# Author: Jeremy Mwenda <jmwenda@bu.edu>
# Desc:
#
# Target platform: Linux
#
# Dependencies
# -----------------
# 1. docker
# 2. sdhash
#
# Installing dependencies
# ----------------------------------
# bash$
#
#####################################################################

import os
import sys
import json
import errno
import subprocess as sub

TEMP_DIR = "/tmp/csdproject"

# cmd is a list: cmd and options if any
def exec_cmd(cmd):
    p = sub.Popen(cmd, stdout=sub.PIPE, stderr=sub.PIPE)
    output, errors = p.communicate()
    if len(errors.strip()) > 0:
        print errors
    return output
    # todo handle errors


def untarlayers(imagedir):
    for d in os.listdir(imagedir):
        layerdir = os.path.join(imagedir, d)
        if os.path.isdir(layerdir):
            layertar = os.path.join(layerdir, 'layer.tar')
            exec_cmd(['tar', '-xvf', layertar, '-C', layerdir])
            os.remove(layertar)


def untar_image(imagetar, imagedir):
    print('untar...')
    exec_cmd(['tar', '-xvf', imagetar, '-C', imagedir])
    os.remove(imagetar)
    untarlayers(imagedir)


def pull_image(imagename):
    print('docker pull...')
    exec_cmd(['docker', 'pull', imagename])


def save_image(imagetar, imagename):
    print('docker save...')
    exec_cmd(['docker', 'save', '-o', imagetar, imagename])


# Read a layer's json file and get ID of parent layer
def get_parent(json_file):
    with open(json_file) as data_file:
        data = json.load(data_file)
        if 'parent' in data:
            return data['parent']
    return None

"""Combine all image layers into a single layer.
If a file exists in multiple layer, only the latest file is kept.
:param dest_dir: full-path output directory.
:param base_path: full-path to directory containing layers
:param layer: directory basename of layer to be parsed
"""
def flatten(dest_dir, base_path, layer):
    json_file = os.path.join(base_path, layer, 'json')        
    with open(json_file) as data_file:
        data = json.load(data_file)
        if 'parent' in data:
            parent = data['parent']
            flatten(dest_dir, base_path, parent) #recursive
                
        print('copying layer -- ', layer)
        layer_path = os.path.join(base_path, layer)        
        os.system('cp -r ' + layer_path + '/* ' + dest_dir)


# Determine leaf layer by checking the json file of each layer..
def get_leaf(imagedir):
    layer_ids = set()
    for f in os.listdir(imagedir):
        # The name of each directory is a layer ID
        if os.path.isdir(os.path.join(imagedir, f)):
            layer_ids.add(f)

    # Layers that are parents
    parents = set()
    for layer_id in layer_ids:
        parent = get_parent(os.path.join(imagedir,layer_id,'json'))
        if parent is not None:
            parents.add(parent)

    # The layer that is not in the list of parents must be a leaf
    leaf = None
    for lid in layer_ids:
        if lid not in parents:
            leaf = lid
    
    print('all_layers:parent_layers -- ', len(layer_ids), ':', len(parents))
    if (len(layer_ids) - len(parents)) != 1 or leaf is None:
        raise # image should only have one leaf
    
    return leaf


def get_leaf_and_flatten(imagedir,dest_dir):
    print('flatenning layers...')
    if not os.path.isdir(dest_dir):
        os.mkdir(flatdir)

    leaf = get_leaf(imagedir)
    flatten(dest_dir, imagedir, leaf)

def make_dir(path):
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise  # raises error
        else:
            pass


# For each file in srcdir, calculate sdhash and write to file in dstdir
# Example: sdhash for file srcdir/usr/local/bin/prog1 will be written to dstdir/usr/local/bin/prog1
def calculate_sdhash(srcdir, dstdir):
    for root, subdirs, files in os.walk(srcdir):
        for subdir in subdirs:
            sub_path = os.path.join(root, subdir)
            sub_dest = sub_path.replace(srcdir, dstdir, 1)
            if not os.path.exists(sub_dest):	
                os.makedirs(os.path.join(sub_dest))

        for filename in files:
            file_path = os.path.join(root, filename)
            file_dest = file_path.replace(srcdir, dstdir, 1)
            gen_sdhash(file_path, file_dest, srcdir)


def gen_sdhash(file_path, file_dest, srcdir):
    os.chdir(srcdir)
    path = file_path.split(srcdir)
    res = exec_cmd(['sdhash', path[1][1:]])
    with open(file_dest, 'w') as f:
        f.write(res)


def hash_and_index(imagename):
    imagetar = os.path.join(TEMP_DIR, 'image.tar')
    imagedir = os.path.join(TEMP_DIR, 'image')
    flat_imgdir = os.path.join(TEMP_DIR, 'flat_image')
    dstdir = os.path.join(TEMP_DIR, 'hashed_image')
    make_dir(TEMP_DIR)
    make_dir(imagedir)
    make_dir(flat_imgdir)
    make_dir(dstdir)

    print imagename
    pull_image(imagename)
    save_image(imagetar, imagename)
    untar_image(imagetar, imagedir)

    get_leaf_and_flatten(imagedir, flat_imgdir)
    calculate_sdhash(flat_imgdir, dstdir)

    #todo cleanup: remove tmp dir


if __name__ == "__main__":
    # imagename should be in the form image:tag
    # Example test: python csdcheck.py python:2.7.8-slim
    imagename = sys.argv[1]

    hash_and_index(imagename)
