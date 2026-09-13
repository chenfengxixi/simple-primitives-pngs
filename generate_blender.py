#!/usr/bin/env python3
"""
generate_blender.py

Blender script to generate PNG renders of simple primitives and produce a zip archive.

Run inside Blender:
  blender --background --python generate_blender.py -- --out out.zip --per_class 20 --resolution 512 --bg white

This script creates the following classes:
- cuboid (rectangular box)
- cube
- sphere
- triangular_pyramid (三棱锥)
- triangular_prism (三棱柱)
- square_pyramid (四棱锥)
- square_prism (四棱柱)
- pentagonal_prism (五棱柱)
- pentagonal_pyramid (五棱锥)
- cylinder
- cone

Outputs:
- out/<class>/*.png
- out/metadata.csv
- out.zip (if --out provided)
"""
import sys
import os
import math
import argparse
import random
import csv
import zipfile

# Blender-specific imports (script must run inside Blender)
import bpy
from mathutils import Vector, Euler

# ---------- Utility functions ----------

def clear_scene():
    # Select and delete all objects
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    # Remove orphan meshes to keep clean
    for mesh in list(bpy.data.meshes):
        try:
            bpy.data.meshes.remove(mesh)
        except Exception:
            pass
    # Remove materials
    for mat in list(bpy.data.materials):
        try:
            bpy.data.materials.remove(mat)
        except Exception:
            pass

def make_camera(location, look_at=(0, 0, 0), focal_length=50):
    cam_data = bpy.data.cameras.new('Camera')
    cam = bpy.data.objects.new('Camera', cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = Vector(location)
    # Point camera to look_at
    direction = Vector(look_at) - cam.location
    if direction.length == 0:
        direction = Vector((0.0, 0.0, -1.0))
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()
    cam.data.lens = focal_length
    bpy.context.scene.camera = cam
    return cam

def make_light(location, strength=5.0):
    light_data = bpy.data.lights.new(name='KeyLight', type='POINT')
    light_data.energy = strength
    light = bpy.data.objects.new(name='KeyLight', object_data=light_data)
    bpy.context.collection.objects.link(light)
    light.location = Vector(location)
    return light

def add_mesh_from_verts_faces(name, verts, faces):
    mesh = bpy.data.meshes.new(name + '_mesh')
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj

# ---------- Primitive generators ----------

def create_prism(n_sides=3, radius=0.5, height=1.0):
    # Regular n-gon prism centered at origin (height along Z)
    verts = []
    faces = []
    # bottom vertices (z = -h/2)
    for i in range(n_sides):
        theta = 2 * math.pi * i / n_sides
        verts.append((radius * math.cos(theta), radius * math.sin(theta), -height / 2))
    # top vertices (z = +h/2)
    for i in range(n_sides):
        theta = 2 * math.pi * i / n_sides
        verts.append((radius * math.cos(theta), radius * math.sin(theta), height / 2))
    # side faces
    for i in range(n_sides):
        a = i
        b = (i + 1) % n_sides
        c = n_sides + (i + 1) % n_sides
        d = n_sides + i
        faces.append((a, b, c, d))
    # bottom face (reverse winding)
    bottom = tuple(range(0, n_sides))
    faces.append(bottom[::-1])
    # top face
    top = tuple(range(n_sides, 2 * n_sides))
    faces.append(top)
    return verts, faces

def create_pyramid(n_sides=3, radius=0.5, height=1.0):
    # Pyramid with regular n-gon base, centered vertically
    verts = []
    faces = []
    base_z = -height / 2
    apex_z = height / 2
    # base verts
    for i in range(n_sides):
        theta = 2 * math.pi * i / n_sides
        verts.append((radius * math.cos(theta), radius * math.sin(theta), base_z))
    # apex
    verts.append((0.0, 0.0, apex_z))
    apex_idx = len(verts) - 1
    # base face (reverse winding)
    base = tuple(range(0, n_sides))
    faces.append(base[::-1])
    # side faces
    for i in range(n_sides):
        a = i
        b = (i + 1) % n_sides
        faces.append((a, b, apex_idx))
    return verts, faces

def create_cuboid(width=1.0, depth=1.0, height=1.0):
    w = width / 2
    d = depth / 2
    h = height / 2
    verts = [(-w, -d, -h), (w, -d, -h), (w, d, -h), (-w, d, -h),
             (-w, -d, h), (w, -d, h), (w, d, h), (-w, d, h)]
    faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    return verts, faces

def create_cone(radius=0.5, height=1.0, segments=32):
    verts = []
    faces = []
    base_z = -height / 2
    apex_z = height / 2
    # circle base
    for i in range(segments):
        theta = 2 * math.pi * i / segments
        verts.append((radius * math.cos(theta), radius * math.sin(theta), base_z))
    # apex
    verts.append((0.0, 0.0, apex_z))
    apex = len(verts) - 1
    # base face
    base = tuple(range(0, segments))
    faces.append(base[::-1])
    # side faces
    for i in range(segments):
        a = i
        b = (i + 1) % segments
        faces.append((a, b, apex))
    return verts, faces

def create_cylinder(radius=0.5, height=1.0, segments=32):
    verts = []
    faces = []
    # bottom circle
    for i in range(segments):
        theta = 2 * math.pi * i / segments
        verts.append((radius * math.cos(theta), radius * math.sin(theta), -height / 2))
    # top circle
    for i in range(segments):
        theta = 2 * math.pi * i / segments
        verts.append((radius * math.cos(theta), radius * math.sin(theta), height / 2))
    # side faces
    for i in range(segments):
        a = i
        b = (i + 1) % segments
        c = segments + (i + 1) % segments
        d = segments + i
        faces.append((a, b, c, d))
    # bottom and top
    faces.append(tuple(range(0, segments))[::-1])
    faces.append(tuple(range(segments, 2 * segments)))
    return verts, faces

# ---------- Transform / helpers ----------

def apply_transform(obj, scale=(1, 1, 1), rot_euler=(0, 0, 0), translation=(0, 0, 0)):
    obj.scale = scale
    obj.rotation_euler = Euler(rot_euler, 'XYZ')
    obj.location = translation

def ensure_dir(p):
    if not os.path.exists(p):
        os.makedirs(p, exist_ok=True)

def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=str, default='out.zip', help='Output zip path')
    parser.add_argument('--per_class', type=int, default=20, help='Images per class')
    parser.add_argument('--resolution', type=int, default=512, help='Image resolution (square)')
    parser.add_argument('--bg', type=str, choices=['white', 'black', 'transparent'], default='white', help='Background')
    args, _ = parser.parse_known_args(argv)
    return args

# ---------- Main ----------

def main(argv):
    args = parse_args(argv)
    per_class = args.per_class
    res = args.resolution
    bg = args.bg
    out_zip = args.out

    workspace = os.getcwd()
    out_dir = os.path.join(workspace, 'out')
    # Clean out_dir if exists
    if os.path.exists(out_dir):
        for root, dirs, files in os.walk(out_dir, topdown=False):
            for name in files:
                try:
                    os.remove(os.path.join(root, name))
                except Exception:
                    pass
            for name in dirs:
                try:
                    os.rmdir(os.path.join(root, name))
                except Exception:
                    pass
    ensure_dir(out_dir)

    # Scene setup
    clear_scene()
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.film_transparent = (bg == 'transparent')

    classes = [
        ('cuboid', lambda: create_cuboid(1.2, 0.8, 0.6)),
        ('cube', lambda: create_cuboid(1.0, 1.0, 1.0)),
        ('sphere', lambda: None),
        ('triangular_pyramid', lambda: create_pyramid(3, radius=0.6, height=1.0)),
        ('triangular_prism', lambda: create_prism(3, radius=0.5, height=1.0)),
        ('square_pyramid', lambda: create_pyramid(4, radius=0.6, height=1.0)),
        ('square_prism', lambda: create_prism(4, radius=0.5, height=1.0)),
        ('pentagonal_prism', lambda: create_prism(5, radius=0.5, height=1.0)),
        ('pentagonal_pyramid', lambda: create_pyramid(5, radius=0.5, height=1.0)),
        ('cylinder', lambda: create_cylinder(0.5, 1.0, segments=64)),
        ('cone', lambda: create_cone(0.5, 1.0, segments=64)),
    ]

    metadata_rows = []

    for cls_name, maker in classes:
        cls_dir = os.path.join(out_dir, cls_name)
        ensure_dir(cls_dir)
        for i in range(per_class):
            # Reset scene for each render
            clear_scene()
            # Create camera and light for this scene
            cam = make_camera((3.0, 0.0, 1.0), look_at=(0, 0, 0), focal_length=50)
            light = make_light((5.0, 5.0, 5.0), strength=5.0)

            # Create mesh
            obj = None
            if cls_name == 'sphere':
                bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0, 0, 0), segments=64, ring_count=32)
                obj = bpy.context.active_object
            else:
                verts_faces = maker()
                if verts_faces is None:
                    continue
                verts, faces = verts_faces
                obj = add_mesh_from_verts_faces(cls_name + '_obj', verts, faces)

            # Random small variation in scale/rotation
            base_scale = 1.0 + random.uniform(-0.15, 0.15)
            sx = base_scale * random.uniform(0.95, 1.05)
            sy = base_scale * random.uniform(0.95, 1.05)
            sz = base_scale * random.uniform(0.95, 1.05)
            rot_z = random.uniform(0, 2 * math.pi)
            rot_x = random.uniform(-0.2, 0.2)
            rot_y = random.uniform(-0.2, 0.2)
            apply_transform(obj, scale=(sx, sy, sz), rot_euler=(rot_x, rot_y, rot_z), translation=(0, 0, 0))

            # Camera viewpoint: sample azimuths around Z
            az = random.uniform(0, 360)
            el = random.uniform(10, 40)
            dist = random.uniform(2.5, 3.5)
            az_rad = math.radians(az)
            el_rad = math.radians(el)
            cam_x = dist * math.cos(az_rad) * math.cos(el_rad)
            cam_y = dist * math.sin(az_rad) * math.cos(el_rad)
            cam_z = dist * math.sin(el_rad)
            cam.location = (cam_x, cam_y, cam_z)
            # Point camera to origin
            direction = Vector((0, 0, 0)) - cam.location
            cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

            # Adjust lighting slightly relative to camera
            light.location = (cam_x * 1.5, cam_y * 1.5, cam_z * 1.2)
            light.data.energy = max(0.1, 3.0 + random.uniform(-1.0, 1.0))

            # Material
            mat = bpy.data.materials.new(name='mat_' + cls_name)
            mat.use_nodes = True
            bsdf = None
            try:
                bsdf = mat.node_tree.nodes.get('Principled BSDF')
            except Exception:
                bsdf = None
            if bsdf:
                bsdf.inputs['Base Color'].default_value = (random.uniform(0.1, 0.9),
                                                           random.uniform(0.1, 0.9),
                                                           random.uniform(0.1, 0.9),
                                                           1)
                bsdf.inputs['Roughness'].default_value = random.uniform(0.2, 0.6)
            # Assign material
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)

            # Render settings
            filename = f"{i:04d}.png"
            filepath = os.path.join(cls_dir, filename)
            scene.render.filepath = filepath

            # Background
            if bg == 'white':
                scene.world.use_nodes = True
                try:
                    bgnode = scene.world.node_tree.nodes.get('Background')
                    if bgnode:
                        bgnode.inputs[0].default_value = (1, 1, 1, 1)
                except Exception:
                    pass
            elif bg == 'black':
                scene.world.use_nodes = True
                try:
                    bgnode = scene.world.node_tree.nodes.get('Background')
                    if bgnode:
                        bgnode.inputs[0].default_value = (0, 0, 0, 1)
                except Exception:
                    pass
            elif bg == 'transparent':
                scene.render.film_transparent = True

            # Render to file
            bpy.ops.render.render(write_still=True)

            # Record metadata
            metadata_rows.append({
                'filename': os.path.relpath(filepath, workspace),
                'class': cls_name,
                'azimuth': az,
                'elevation': el,
                'cam_distance': dist,
                'scale_x': sx,
                'scale_y': sy,
                'scale_z': sz,
                'rot_z': rot_z
            })

    # Write metadata CSV
    meta_path = os.path.join(out_dir, 'metadata.csv')
    with open(meta_path, 'w', newline='') as csvfile:
        fieldnames = ['filename', 'class', 'azimuth', 'elevation', 'cam_distance', 'scale_x', 'scale_y', 'scale_z', 'rot_z']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for r in metadata_rows:
            writer.writerow(r)

    # Zip output directory
    if out_zip:
        zip_path = os.path.join(workspace, out_zip) if not os.path.isabs(out_zip) else out_zip
        zipf = zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED)
        for root, dirs, files in os.walk(out_dir):
            for file in files:
                full = os.path.join(root, file)
                arc = os.path.relpath(full, out_dir)
                zipf.write(full, arcname=arc)
        zipf.close()
        print('Wrote', zip_path)

if __name__ == '__main__':
    argv = sys.argv
    if '--' in argv:
        idx = argv.index('--')
        argv = argv[idx + 1:]
    else:
        argv = []
    main(argv)
