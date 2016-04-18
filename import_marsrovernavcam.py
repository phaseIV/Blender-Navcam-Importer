import os
import re
import math
import time
import struct
from urllib import request
from datetime import datetime

import numpy as np
import mathutils
from mathutils import Vector, Quaternion
from planetaryimage import PDS3Image

import bpy
import bmesh



bl_info = {
    "name": "Mars Rover NAVCAM Import",
    "author": "Rob Haarsma (rob@captainvideo.nl)",
    "version": (0, 1, 4),
    "blender": (2, 7, 1),
    "location": "File > Import > ...  and/or  Tools menu > Misc > Mars Rover NAVCAM Import",
    "description": "Creates textured meshes of Martian surfaces from Mars Rover Navcam image products",
    "warning": "This script produces high poly meshes and saves downloaded data in Temp directory",
    "wiki_url": "https://github.com/phaseIV/Blender-Navcam-Importer",
    "tracker_url": "https://github.com/phaseIV/Blender-Navcam-Importer/issues",
    "category": "Import-Export"}

pdsimg_path = 'http://pdsimg.jpl.nasa.gov/data/'
nasaimg_path = 'http://mars.nasa.gov/'

roverDataDir = []
roverImageDir = []
local_data_dir = []
local_file = []

popup_error = None


class NavcamDialogOperator(bpy.types.Operator):
    bl_idname = "io.navcamdialog_operator"
    bl_label = "Enter Rover Navcam image ID"

    navcam_string = bpy.props.StringProperty(name="Image Name", default='')
    fillhole_bool = bpy.props.BoolProperty(name="Fill Gaps (draft)",
                                           default=True)
    # filllength_float = bpy.props.FloatProperty(name="Max Fill Length", 
    # min=0.001, max=100.0)

    def execute(self, context):
        ReadNavcamString(self.navcam_string, self.fillhole_bool)
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=600)


def ReadNavcamString(inString, inFillBool):
    global local_data_dir, roverDataDir, roverImageDir, popup_error

    if inString == "":
        return

    time_start = time.time()

    SetRenderSettings()
    local_data_dir = os.path.join(
        bpy.context.user_preferences.filepaths.temporary_directory,
        'MarsRoverImages/'
    )

    collString = inString.split(",")
    for i in range(0, len(collString)):
        if(len(collString[i]) == 0):
            collString.pop(i)

    for i in range(0, len(collString)):
        theString = os.path.splitext(collString[i].strip(' '))[0]

        if len(theString) == 27 or len(theString) == 36:
            pass
        else:
            popup_error = 3
            bpy.context.window_manager.popup_menu(
                draw, title="Name Error", icon='ERROR'
            )
            return

        rover = None

        if theString.startswith('N'):
            rover = 3
        if theString.startswith('2N'):
            rover = 1
        if theString.startswith('1N'):
            rover = 2

        if rover is None:
            popup_error = 4
            bpy.context.window_manager.popup_menu(
                draw, title="Name Error", icon='ERROR'
            )
            return

        if rover == 1:
            roverDataDir = 'mer/mer2no_0xxx/data/'
            roverImageDir = 'mer/gallery/all/2/n/'
        if rover == 2:
            roverDataDir = 'mer/mer1no_0xxx/data/'
            roverImageDir = 'mer/gallery/all/1/n/'
        if rover == 3:
            roverDataDir = 'msl/MSLNAV_1XXX/DATA/'
            roverImageDir = 'msl/MSLNAV_1XXX/EXTRAS/FULL/'

        sol_ref = tosol(rover, theString)

        print('\nConstructing mesh %d/%d, sol %d, name %s' %
              (i + 1, len(collString), sol_ref, theString)
              )

        image_texture_filename = get_texture_image(rover, sol_ref, theString)
        if image_texture_filename is None:
            popup_error = 1
            bpy.context.window_manager.popup_menu(draw, title="URL Error", icon='ERROR')
            return

        image_depth_filename = get_depth_image(rover, sol_ref, theString)

        if image_depth_filename is None:
            popup_error = 2
            bpy.context.window_manager.popup_menu(draw, title="URL Error", icon='ERROR')
            return

        create_mesh_from_depthimage(
            rover,
            sol_ref,
            image_depth_filename,
            image_texture_filename,
            inFillBool
        )

    elapsed = float(time.time() - time_start)
    print("Script execution time: %s" % time.strftime('%H:%M:%S', time.gmtime(elapsed)))


def SetRenderSettings():
    rnd = bpy.data.scenes[0].render
    rnd.resolution_x = 1024
    rnd.resolution_y = 1024
    rnd.resolution_percentage = 100
    rnd.tile_x = 512
    rnd.tile_y = 512
    rnd.use_raytrace = False
    bpy.context.scene.world.horizon_color = (0.02, 0.02, 0.02)


def download_file(url):
    global localfile

    proper_url = url.replace('\\', '/')

    try:
        page = request.urlopen(proper_url)

        if page.getcode() is not 200:
            # print('Tried to download data from %s and got http response code %s', url,
            #      str(page.getcode()))
            return False

        request.urlretrieve(proper_url, localfile)

        return True

    except:
        return False


def tosol(rover, nameID):
    # origin: https://github.com/natronics/MSL-Feed/blob/master/nasa.py
    # function hacked to return sol from image filename

    craft_time = None

    if rover == 3:
        craft_time = nameID[4:13]
    if rover == 2 or rover == 1:
        craft_time = nameID[2:11]

    s = int(craft_time)
    MSD = (s/88775.244) + 44795.9998

    sol = MSD - 49269.2432411704
    sol = sol + 1  # for sol 0
    sol = int(math.ceil(sol))

    deviate = None

    if rover == 3:
        deviate = -6
    if rover == 2:
        deviate = 3028
    if rover == 1:
        deviate = 3048

    return sol+deviate


def get_texture_image(rover, sol, imgname):
    global roverImageDir, local_data_dir, localfile

    if rover == 3:
        if sol > 450:
            texname = '%s.PNG' % (imgname)
        else:
            texname = '%s.JPG' % (imgname)
    else:
        texname = '%s.JPG' % (imgname)

    s = list(texname)

    if rover == 3:
        s[13] = 'R'
        s[14] = 'A'
        s[15] = 'S'
        s[35] = '1'
    else:
        if s[18] == 'F' or s[18] == 'f':
            # mer downsampled??
            s[11] = 'e'
            s[12] = 'd'
            s[13] = 'n'
            s[25] = 'm'
        else:
            s[11] = 'e'
            s[12] = 'f'
            s[13] = 'f'
            s[25] = 'm'

    imagename = '%s' % "".join(s)
    imgfilename = os.path.join(local_data_dir, roverImageDir, '%05d' % (sol), imagename)

    if os.path.isfile(imgfilename):
        print('tex from cache: ', imgfilename)
        return imgfilename

    retrievedir = os.path.join(
        os.path.dirname(local_data_dir), roverImageDir, '%05d' % (sol)
    )
    if not os.path.exists(retrievedir):
        os.makedirs(retrievedir)

    localfile = imgfilename

    if rover == 2 or rover == 1:
        remotefile = os.path.join(
            os.path.dirname(nasaimg_path),
            roverImageDir,
            '%03d' % (sol),
            imagename.upper()
        )

    if rover == 3:
        remotefile = os.path.join(
            os.path.dirname(pdsimg_path),
            roverImageDir,
            'SOL%05d' % (sol),
            imagename
        )

    print('downloading tex: ', remotefile)

    result = download_file(remotefile)

    if result is False:
        return None

    if os.path.isfile(localfile):
        return imgfilename


def get_depth_image(rover, sol, imgname):
    global roverDataDir, local_data_dir, localfile

    xyzname = '%s.IMG' % (imgname)
    s = list(xyzname)

    if rover == 3:
        s[13] = 'X'
        s[14] = 'Y'
        s[15] = 'Z'
        s[35] = '1'
    else:
        s[11] = 'x'
        s[12] = 'y'
        s[13] = 'l'
        s[25] = 'm'

    xyzname = '%s' % "".join(s)
    xyzfilename = os.path.join(
        local_data_dir, roverDataDir, 'sol%05d' % (sol), xyzname
    )

    if os.path.isfile(xyzfilename):
        print('xyz from cache: ', xyzfilename)
        return xyzfilename

    retrievedir = os.path.join(
        local_data_dir, roverDataDir, 'sol%05d' % (sol)
    )
    if not os.path.exists(retrievedir):
        os.makedirs(retrievedir)

    localfile = xyzfilename

    if rover == 2 or rover == 1:
        remotefile = os.path.join(
            os.path.dirname(pdsimg_path),
            roverDataDir,
            'sol%04d' % (sol),
            'rdr',
            xyzname.lower()
        )
    if rover == 3:
        remotefile = os.path.join(
            os.path.dirname(pdsimg_path),
            roverDataDir,
            'SOL%05d' % (sol),
            xyzname
        )

    print('downloading xyz: ', remotefile)

    result = download_file(remotefile)
    if result is False:
        return None

    if os.path.isfile(localfile):
        return xyzfilename


def create_mesh_from_depthimage(rover, sol, image_depth_filename,
                                image_texture_filename, do_fill):
    # snippets used from:
    # https://svn.blender.org/svnroot/bf-extensions/contrib/py/scripts/addons/io_import_LRO_Lola_MGS_Mola_img.py
    # https://arsf-dan.nerc.ac.uk/trac/attachment/wiki/Processing/SyntheticDataset/data_handler.py

    # This whole func needs a refactor BAD-LY

    if image_depth_filename == '':
        return

    FileAndPath = image_depth_filename
    FileAndExt = os.path.splitext(FileAndPath)

    print('creating mesh...')

    try:
        if FileAndExt[1].isupper():
            image = PDS3Image.open(FileAndExt[0] + ".IMG")
            label = image.label
        else:
            image = PDS3Image.open(FileAndExt[0] + ".img")
            label = image.label
    except:
        print("Error opening %s" % image_depth_filename)
        return

    bCam = Vector((0.0, 0.0, 0.0))
    bCamQuad = Quaternion((0.0, 0.0, 0.0, 0.0))
    bCamVec = Vector((0.0, 0.0, 0.0))
    bRoverVec = Vector((0.0, 0.0, 0.0))
    bRoverQuad = Quaternion((0.0, 0.0, 0.0, 0.0))

    creation_date = label['START_TIME'].strftime("%Y-%m-%dT%H:%M:%S.%f")
    LINES = label['IMAGE']['LINES']
    LINE_SAMPLES = label['IMAGE']['LINE_SAMPLES']
    SAMPLE_TYPE = label['IMAGE']['SAMPLE_TYPE']
    SAMPLE_BITS = label['IMAGE']['SAMPLE_BITS']
    BYTES = label['IMAGE_HEADER']['BYTES']

    osv = label['ROVER_COORDINATE_SYSTEM']['ORIGIN_OFFSET_VECTOR']
    # GODBER TODO: Understand why these are different, must be
    # different covention
    bRoverVec[:] = osv[1], osv[0], -osv[2]
    bRoverQuad[:] = label['ROVER_COORDINATE_SYSTEM']['ORIGIN_ROTATION_QUATERNION']
    mc1 = label['GEOMETRIC_CAMERA_MODEL']['MODEL_COMPONENT_1']
    bCam[:] = mc1[1], mc1[0], - mc1[2]

    # these values were not found in the label for the MSL NAVCAM, perhaps they
    # are needed for MER NAVCAM.
    # UNIT = label['IMAGE']['UNIT']
    # bCamQuad[:] = label['GEOMETRIC_CAMERA_MODEL']['MODEL_TRANSFORM_QUATERNION']
    # bCamVec[:] = label['GEOMETRIC_CAMERA_MODEL']['MODEL_TRANSFORM_VECTOR']

    Faces = []

    Vertex = generate_vertex_pds(image)

    if do_fill:
        print("Deholing Vertex of length: ", len(Vertex))
        Vertex = simple_dehole(Vertex, LINES, LINE_SAMPLES)

    for j in range(0, LINES-1):
        for k in range(0, LINE_SAMPLES-1):
            Faces.append((
                (j * LINE_SAMPLES + k),
                (j * LINE_SAMPLES + k + 1),
                ((j + 1) * LINE_SAMPLES + k + 1), ((j + 1) * LINE_SAMPLES + k)
            ))

    os.path.basename(FileAndExt[0])
    TARGET_NAME = '%s-%s' % (sol, os.path.basename(FileAndExt[0]))
    mesh = bpy.data.meshes.new(TARGET_NAME)
    TARGET_NAME = mesh.name
    mesh.from_pydata(Vertex, [], Faces)

    del Vertex
    del Faces
    mesh.update()

    print('texturing mesh...')

    ob_new = bpy.data.objects.new(TARGET_NAME, mesh)
    ob_new.data = mesh

    scene = bpy.context.scene
    scene.objects.link(ob_new)
    scene.objects.active = ob_new
    ob_new.select = True

    obj = bpy.context.object

    try:
        with open(image_texture_filename):
            img = bpy.data.images.load(image_texture_filename)
            cTex = bpy.data.textures.new(
                'Tex-' + os.path.basename(FileAndExt[0]), type='IMAGE'
            )
            cTex.image = img
            img.pack(as_png=False)

            me = obj.data
            me.show_double_sided = True
            bpy.ops.mesh.uv_texture_add()

            if me.uv_textures.active is None:
                uv_tex = me.uv_textures.new().data
            else:
                uv_tex = me.uv_textures.active.data

            for poly in uv_tex:
                poly.image = img

            # Create shadeless material and MTex
            the_mat = bpy.data.materials.new('Mat-' + os.path.basename(FileAndExt[0]))
            the_mat.use_shadeless = True

            mtex = the_mat.texture_slots.add()
            mtex.texture = cTex
            mtex.texture.extension = 'CLIP'
            mtex.texture_coords = 'UV'

            # add material to object
            obj.data.materials.append(the_mat)
    except IOError:
        print('Oh dear. Missing %s' % (imgfilename))

    uvteller = 0

    # per face !
    for j in range(0, LINES - 1):
        for k in range(0, LINE_SAMPLES - 1):
            tc1 = Vector(((1.0 / LINE_SAMPLES) * k, 1.0 - (1.0 / LINES) * j))
            tc2 = Vector(((1.0 / LINE_SAMPLES) * (k + 1), 1.0 - (1.0 / LINES) * j))
            tc3 = Vector(((1.0 / LINE_SAMPLES) * (k + 1), 1.0 - (1.0 / LINES) * (j + 1)))
            tc4 = Vector(((1.0 / LINE_SAMPLES) * k, 1.0 - (1.0 / LINES) * (j + 1)))

            bpy.data.objects[TARGET_NAME].data.uv_layers[0].data[uvteller].uv = tc1
            uvteller = uvteller + 1
            bpy.data.objects[TARGET_NAME].data.uv_layers[0].data[uvteller].uv = tc2
            uvteller = uvteller + 1
            bpy.data.objects[TARGET_NAME].data.uv_layers[0].data[uvteller].uv = tc3
            uvteller = uvteller + 1
            bpy.data.objects[TARGET_NAME].data.uv_layers[0].data[uvteller].uv = tc4
            uvteller = uvteller + 1

    bpy.ops.object.mode_set(mode='EDIT')
    # Get the active mesh
    mesh_ob = bpy.context.object
    me = mesh_ob.data
    bm = bmesh.from_edit_mesh(me)

    verts = [v for v in bm.verts if v.co[0] == 0.0 and v.co[1] == 0.0 and v.co[2] == 0.0]
    bmesh.ops.delete(bm, geom=verts, context=1)
    bmesh.update_edit_mesh(me)

    bpy.ops.object.mode_set(mode='EDIT')
    # Get the active mesh
    mesh_ob = bpy.context.object
    me = mesh_ob.data
    bm = bmesh.from_edit_mesh(me)

    verts = [v for v in bm.verts if len(v.link_faces) == 0]
    bmesh.ops.delete(bm, geom=verts, context=1)
    bmesh.update_edit_mesh(me)

    bpy.ops.object.editmode_toggle()

    '''
    #smooth modifier prop
    if smooth:
        bpy.ops.object.modifier_add(type='SMOOTH')
        bpy.context.active_object.modifiers['Smooth'].factor=smoothfac_ref
        bpy.context.active_object.modifiers['Smooth'].iterations=smoothrepeat_ref
        bpy.ops.object.modifier_apply(modifier='Smooth')

    #decimate modifier prop
    if decimate:
        bpy.ops.object.modifier_add(type='DECIMATE')
        bpy.context.active_object.modifiers['Decimate'].ratio=decimate_ref
        bpy.ops.object.modifier_apply(modifier='Decimate')
    '''

    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')
    bpy.ops.object.mode_set(mode='OBJECT')

    # mesh generation is done here, adding camera and text follows

    cam = bpy.data.cameras.new('Camera')
    cam_ob = bpy.data.objects.new('Cam-' + os.path.basename(FileAndExt[0]), cam)

    bRoverVec = bRoverVec * 0.1

    mat_loc = mathutils.Matrix.Translation(bRoverVec)
    mat_trans = mathutils.Matrix.Translation((0.0, 0.0, 0.15))

    cam_ob.matrix_world = mat_loc * mat_trans

    # Create Credit text
    trover = ['Spirit', 'Opportunity', 'Curiosity']

    if creation_date.startswith('\"'):
        date_object = datetime.strptime(creation_date[1:23], '%Y-%m-%dT%H:%M:%S.%f')
    else:
        date_object = datetime.strptime(creation_date[0:22], '%Y-%m-%dT%H:%M:%S.%f')

    # MSL provides Right Navcam Depth data
    s = list(os.path.basename(image_texture_filename))
    if rover == 2 or rover == 1:
        if s[23] == 'L' or s[23] == 'l':
            whichcam = 'Left'
        else:
            whichcam = 'Right'

    if rover == 3:
        if s[1] == 'L' or s[1] == 'l':
            whichcam = 'Left'
        else:
            whichcam = 'Right'

    tagtext = trover[rover - 1] + ' ' + whichcam + ' Navcam Image at Sol ' + \
        str(sol) + '\n' + str(date_object.strftime('%d %b %Y %H:%M:%S')) + \
        ' UTC\nNASA / JPL-CALTECH / phaseIV'

    bpy.ops.object.text_add(enter_editmode=True, location=(-0.02, -0.0185, -0.05))
    bpy.ops.font.delete()
    bpy.ops.font.text_insert(text=str(tagtext))
    bpy.ops.object.editmode_toggle()

    textSize = 0.001
    text_ob = bpy.context.scene.objects.active
    text_ob.scale = [textSize, textSize, textSize]

    found = None

    for i in range(len(bpy.data.materials)):
        if bpy.data.materials[i].name == 'White text':
            mat = bpy.data.materials[i]
            found = True

    if not found:
        mat = bpy.data.materials.new(name="White text")
        mat.use_shadeless = True
        mat.diffuse_color = [1.0, 1.0, 1.0]

    text_ob.data.materials.append(mat)
    text_ob.parent = cam_ob

    objloc = Vector(mesh_ob.location)
    rovloc = Vector(bRoverVec)
    distvec = rovloc - objloc

    expoint = obj.matrix_world.to_translation() + \
        Vector((0.0, 0.0, -0.04 - distvec.length * 0.1))
    look_at(cam_ob, expoint)

    bpy.context.scene.objects.link(cam_ob)
    bpy.context.scene.camera = cam_ob
    bpy.context.scene.update()

    cam.clip_start = 0.01
    cam.draw_size = 0.1

    print ('mesh generation complete.')
    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)


def generate_vertex_pds(image):
    """Generate a List of Location Vectors from the provided PDS Image

    Given a PDS image, this should retrun a list of Vectors containing the X, Y,
    Z coordinates of each pixel in the image.
    """
    Vertex = []
    vec_scale_factor = 0.1  # no idea why
    lines = image.label['IMAGE']['LINES']
    line_samples = image.label['IMAGE']['LINE_SAMPLES']

    img = vec_scale_factor * np.dstack(
        (image.image[:, :, 1], image.image[:, :, 0], -image.image[:, :, 2])
    )

    for line in range(0, lines):
        for line_sample in range(0, line_samples):
            vec = Vector(img[line, line_sample, :])
            Vertex.append(vec)

    return Vertex


def simple_dehole(Vertex, LINES, LINE_SAMPLES):
    # simple dehole (bridge)
    # max_fill_length = fill_length
    nulvec = Vector((0.0, 0.0, 0.0))
    max_fill_length = 0.6

    for j in range(0, LINES-1):
        for k in range(0, LINE_SAMPLES - 1):
            if Vertex[j * LINE_SAMPLES + k] != nulvec:
                m = 1
                while Vertex[(j + m) * LINE_SAMPLES + k] == nulvec and (j + m) < LINES-1:
                    m = m + 1

                if m != 1 and Vertex[(j + m) * LINE_SAMPLES + k] != nulvec:
                    VertexA = Vertex[j * LINE_SAMPLES + k]
                    VertexB = Vertex[(j + m) * LINE_SAMPLES + k]
                    sparevec = VertexB - VertexA
                    if sparevec.length < max_fill_length:
                        for n in range(0, m):
                            Vertex[(j + n) * LINE_SAMPLES + k] = VertexA + \
                                                                 (sparevec / m) * n

    return Vertex


def look_at(obj_camera, point):
    loc_camera = obj_camera.matrix_world.to_translation()

    direction = point - loc_camera
    # point the cameras '-Z' and use its 'Y' as up
    rot_quat = direction.to_track_quat('-Z', 'Y')

    # assume we're using euler rotation
    obj_camera.rotation_euler = rot_quat.to_euler()


def draw(self, context):
    global popup_error

    if(popup_error == 1):
        self.layout.label("Unable to retrieve NAVCAM texture image.")
        print("Unable to retrieve NAVCAM texture image.")

    if(popup_error == 2):
        self.layout.label("Unable to retrieve NAVCAM depth image.")
        print("Unable to retrieve NAVCAM depth image.")

    if(popup_error == 3):
        self.layout.label("Navcam imagename has incorrect length.")
        print("Navcam imagename has incorrect length.")

    if(popup_error == 4):
        self.layout.label("Not a valid Left Navcam imagename.")
        print("Not a valid Left Navcam imagename.")


class NavcamToolsPanel(bpy.types.Panel):
    bl_label = "Mars Rover Import"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"

    def draw(self, context):
        self.layout.operator("io.navcamdialog_operator")


def menu_func_import(self, context):
    self.layout.operator(NavcamDialogOperator.bl_idname, text="Mars Rover NAVCAM Import")


def register():
    bpy.utils.register_class(NavcamDialogOperator)
    bpy.types.INFO_MT_file_import.append(menu_func_import)
    bpy.utils.register_class(NavcamToolsPanel)


def unregister():
    bpy.utils.unregister_class(NavcamDialogOperator)
    bpy.types.INFO_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(NavcamToolsPanel)


if __name__ == "__main__":
    register()
