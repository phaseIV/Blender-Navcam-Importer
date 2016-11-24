import bpy
import os
import math
import mathutils
from mathutils import Vector, Quaternion
import struct
import bmesh
from urllib import request
import time
import re
from datetime import datetime


bl_info = {
    "name": "Mars Rover NAVCAM Import",
    "author": "Rob Haarsma (rob@captainvideo.nl)",
    "version": (0, 1, 6),
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
curve_minval = None
curve_maxval = None


class NavcamDialogOperator(bpy.types.Operator):
    bl_idname = "io.navcamdialog_operator"
    bl_label = "Enter Rover Navcam image ID"

    navcam_string = bpy.props.StringProperty(name="Image Name", default='')
    fillhole_bool = bpy.props.BoolProperty(
        name="Fill Gaps (draft)", default=True)
    radimage_bool = bpy.props.BoolProperty(
        name="Use 16bit RAD texture", default=False)
    #filllength_float = bpy.props.FloatProperty(name="Max Fill Length", min=0.001, max=100.0)

    def execute(self, context):
        ReadNavcamString(self.navcam_string,
                         self.fillhole_bool, self.radimage_bool)
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=650)


def ReadNavcamString(inString, inFillBool, inRadBool):
    global local_data_dir, roverDataDir, roverImageDir, popup_error

    if inString == "":
        return

    time_start = time.time()

    SetRenderSettings()
    local_data_dir = os.path.join(
        bpy.context.user_preferences.filepaths.temporary_directory, 'MarsRoverImages/')

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
                draw, title="Name Error", icon='ERROR')
            return

        rover = None

        if theString.startswith('N'):
            rover = 3
        if theString.startswith('2N'):
            rover = 1
        if theString.startswith('1N'):
            rover = 2

        if rover == None:
            popup_error = 4
            bpy.context.window_manager.popup_menu(
                draw, title="Name Error", icon='ERROR')
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
              (i + 1, len(collString), sol_ref, theString))

        if inRadBool:
            image_16bit_texture_filename = get_16bit_texture_image(
                rover, sol_ref, theString)
            image_texture_filename = convert_to_png(
                image_16bit_texture_filename)
        else:
            image_texture_filename = get_texture_image(
                rover, sol_ref, theString)

        if (image_texture_filename == None):
            popup_error = 1
            bpy.context.window_manager.popup_menu(
                draw, title="URL Error", icon='ERROR')
            return

        image_depth_filename = get_depth_image(rover, sol_ref, theString)
        if (image_depth_filename == None):
            popup_error = 2
            bpy.context.window_manager.popup_menu(
                draw, title="URL Error", icon='ERROR')
            return

        create_mesh_from_depthimage(
            rover, sol_ref, image_depth_filename, image_texture_filename, inFillBool, inRadBool)

    elapsed = float(time.time() - time_start)
    print("Script execution time: %s" %
          time.strftime('%H:%M:%S', time.gmtime(elapsed)))


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
    MSD = (s / 88775.244) + 44795.9998

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

    return sol + deviate


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
    imgfilename = os.path.join(
        local_data_dir, roverImageDir, '%05d' % (sol), imagename)

    if os.path.isfile(imgfilename):
        print('tex from cache: ', imgfilename)
        return imgfilename

    retrievedir = os.path.join(os.path.dirname(
        local_data_dir), roverImageDir, '%05d' % (sol))
    if not os.path.exists(retrievedir):
        os.makedirs(retrievedir)

    localfile = imgfilename

    if rover == 2 or rover == 1:
        remotefile = os.path.join(os.path.dirname(
            nasaimg_path), roverImageDir, '%03d' % (sol), imagename.upper())
    if rover == 3:
        remotefile = os.path.join(os.path.dirname(
            pdsimg_path), roverImageDir, 'SOL%05d' % (sol), imagename)

    print('downloading tex: ', remotefile)

    result = download_file(remotefile)
    if(result == False):
        return None

    if os.path.isfile(localfile):
        return imgfilename


def get_16bit_texture_image(rover, sol, imgname):
    global roverImageDir, local_data_dir, localfile

    texname = '%s.IMG' % (imgname)
    s = list(texname)

    if rover == 3:
        s[13] = 'R'
        s[14] = 'A'
        s[15] = 'D'
        s[35] = '1'
    else:
        s[11] = 'm'
        s[12] = 'r'
        s[13] = 'd'
        s[25] = 'm'

    imagename = '%s' % "".join(s)
    imgfilename = os.path.join(
        local_data_dir, roverDataDir, 'sol%05d' % (sol), imagename)

    if os.path.isfile(imgfilename):
        print('rad from cache: ', imgfilename)
        return imgfilename

    retrievedir = os.path.join(os.path.dirname(
        local_data_dir), roverDataDir, 'sol%05d' % (sol))
    if not os.path.exists(retrievedir):
        os.makedirs(retrievedir)

    localfile = imgfilename

    if rover == 2 or rover == 1:
        remotefile = os.path.join(os.path.dirname(
            pdsimg_path), roverDataDir, 'sol%04d' % (sol), 'rdr', imagename.lower())
    if rover == 3:
        remotefile = os.path.join(os.path.dirname(
            pdsimg_path), roverDataDir, 'SOL%05d' % (sol), imagename)

    print('downloading rad: ', remotefile)

    result = download_file(remotefile)
    if(result == False):
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
        local_data_dir, roverDataDir, 'sol%05d' % (sol), xyzname)

    if os.path.isfile(xyzfilename):
        print('xyz from cache: ', xyzfilename)
        return xyzfilename

    retrievedir = os.path.join(local_data_dir, roverDataDir, 'sol%05d' % (sol))
    if not os.path.exists(retrievedir):
        os.makedirs(retrievedir)

    localfile = xyzfilename

    if rover == 2 or rover == 1:
        remotefile = os.path.join(os.path.dirname(
            pdsimg_path), roverDataDir, 'sol%04d' % (sol), 'rdr', xyzname.lower())
    if rover == 3:
        remotefile = os.path.join(os.path.dirname(
            pdsimg_path), roverDataDir, 'SOL%05d' % (sol), xyzname)

    print('downloading xyz: ', remotefile)

    result = download_file(remotefile)
    if(result == False):
        return None

    if os.path.isfile(localfile):
        return xyzfilename


def convert_to_png(image_16bit_texture_filename):
    global curve_minval, curve_maxval

    LINES = LINE_SAMPLES = SAMPLE_BITS = BYTES = 0
    SAMPLE_TYPE = ""

    FileAndPath = image_16bit_texture_filename
    FileAndExt = os.path.splitext(FileAndPath)

    print('creating png...')

    # Open the img file (ascii label part)
    try:
        if FileAndExt[1].isupper():
            f = open(FileAndExt[0] + ".IMG", 'r')
        else:
            f = open(FileAndExt[0] + ".img", 'r')
    except:
        return

    block = ""
    OFFSET = 0
    for line in f:
        if line.strip() == "END":
            break
        tmp = line.split("=")
        if tmp[0].strip() == "OBJECT" and tmp[1].strip() == "IMAGE":
            block = "IMAGE"
        elif tmp[0].strip() == "END_OBJECT" and tmp[1].strip() == "IMAGE":
            block = ""
        if tmp[0].strip() == "OBJECT" and tmp[1].strip() == "IMAGE_HEADER":
            block = "IMAGE_HEADER"
        elif tmp[0].strip() == "END_OBJECT" and tmp[1].strip() == "IMAGE_HEADER":
            block = ""

        if block == "IMAGE":
            if line.find("LINES") != -1 and not(line.startswith("/*")):
                tmp = line.split("=")
                LINES = int(tmp[1].strip())
            elif line.find("LINE_SAMPLES") != -1 and not(line.startswith("/*")):
                tmp = line.split("=")
                LINE_SAMPLES = int(tmp[1].strip())
            elif line.find("SAMPLE_TYPE") != -1 and not(line.startswith("/*")):
                tmp = line.split("=")
                SAMPLE_TYPE = tmp[1].strip()
            elif line.find("SAMPLE_BITS") != -1 and not(line.startswith("/*")):
                tmp = line.split("=")
                SAMPLE_BITS = int(tmp[1].strip())

        if block == "IMAGE_HEADER":
            if line.find("BYTES") != -1 and not(line.startswith("/*")):
                tmp = line.split("=")
                BYTES = int(tmp[1].strip())

    f.close

    # Open the img file (binary data part)
    try:
        if FileAndExt[1].isupper():
            f2 = open(FileAndExt[0] + ".IMG", 'rb')
        else:
            f2 = open(FileAndExt[0] + ".img", 'rb')
    except:
        return

    edit = f2.read()
    meh = edit.find(b'LBLSIZE')
    f2.seek(meh + BYTES)

    bands = []
    for bandnum in range(0, 1):

        bands.append([])
        for linenum in range(0, LINES):

            bands[bandnum].append([])
            for pixnum in range(0, LINE_SAMPLES):

                dataitem = f2.read(2)
                if (dataitem == ""):
                    print ('ERROR, Ran out of data to read before we should have')

                bands[bandnum][linenum].append(
                    struct.unpack(">H", dataitem)[0])

    f2.close

    pixels = [None] * LINES * LINE_SAMPLES

    curve_minval = 1.0
    curve_maxval = 0.0

    for j in range(0, LINES):
        for k in range(0, LINE_SAMPLES):

            r = g = b = float(bands[0][LINES - 1 - j]
                              [k] & 0xffff) / (32768 * 2)
            a = 1.0
            pixels[(j * LINES) + k] = [r, g, b, a]

            if r > curve_maxval:
                curve_maxval = r
            if r < curve_minval:
                curve_minval = r

    del bands

    pixels = [chan for px in pixels for chan in px]
    pngname = FileAndExt[0] + '.PNG'

    # modify scene for png export
    scene = bpy.data.scenes[0]
    settings = scene.render.image_settings
    settings.color_depth = '16'
    settings.color_mode = 'BW'
    settings.file_format = 'PNG'

    image = bpy.data.images.new(os.path.basename(
        FileAndExt[0]), LINES, LINE_SAMPLES, float_buffer=True)
    image.pixels = pixels
    image.file_format = 'PNG'
    image.save_render(pngname, scene)

    settings.color_depth = '8'
    settings.color_mode = 'RGBA'

    # remove converted image from Blender, it will be reloaded
    bpy.data.images.remove(image)
    del pixels

    return pngname


def create_mesh_from_depthimage(rover, sol, image_depth_filename, image_texture_filename, do_fill, do_rad):
    # snippets used from:
    # https://svn.blender.org/svnroot/bf-extensions/contrib/py/scripts/addons/io_import_LRO_Lola_MGS_Mola_img.py
    # https://arsf-dan.nerc.ac.uk/trac/attachment/wiki/Processing/SyntheticDataset/data_handler.py

    # This whole func needs a refactor BAD-LY

    global curve_minval, curve_maxval

    bRoverVec = Vector((0.0, 0.0, 0.0))

    if image_depth_filename == '':
        return

    creation_date = None
    LINES = LINE_SAMPLES = SAMPLE_BITS = 0
    SAMPLE_TYPE = ""

    FileAndPath = image_depth_filename
    FileAndExt = os.path.splitext(FileAndPath)

    print('creating mesh...')

    # Open the img label file (ascii label part)
    try:
        if FileAndExt[1].isupper():
            f = open(FileAndExt[0] + ".IMG", 'r')
        else:
            f = open(FileAndExt[0] + ".img", 'r')
    except:
        return

    block = ""
    OFFSET = 0
    for line in f:
        if line.strip() == "END":
            break
        tmp = line.split("=")
        if tmp[0].strip() == "OBJECT" and tmp[1].strip() == "IMAGE":
            block = "IMAGE"
        elif tmp[0].strip() == "END_OBJECT" and tmp[1].strip() == "IMAGE":
            block = ""
        if tmp[0].strip() == "OBJECT" and tmp[1].strip() == "IMAGE_HEADER":
            block = "IMAGE_HEADER"
        elif tmp[0].strip() == "END_OBJECT" and tmp[1].strip() == "IMAGE_HEADER":
            block = ""
        if tmp[0].strip() == "GROUP" and tmp[1].strip() == "ROVER_COORDINATE_SYSTEM":
            block = "ROVER_COORDINATE_SYSTEM"
        elif tmp[0].strip() == "END_GROUP" and tmp[1].strip() == "ROVER_COORDINATE_SYSTEM":
            block = ""

        elif tmp[0].strip() == "START_TIME":
            creation_date = str(tmp[1].strip())

        if block == "IMAGE":
            if line.find("LINES") != -1 and not(line.startswith("/*")):
                tmp = line.split("=")
                LINES = int(tmp[1].strip())
            elif line.find("LINE_SAMPLES") != -1 and not(line.startswith("/*")):
                tmp = line.split("=")
                LINE_SAMPLES = int(tmp[1].strip())
            elif line.find("SAMPLE_TYPE") != -1 and not(line.startswith("/*")):
                tmp = line.split("=")
                SAMPLE_TYPE = tmp[1].strip()
            elif line.find("SAMPLE_BITS") != -1 and not(line.startswith("/*")):
                tmp = line.split("=")
                SAMPLE_BITS = int(tmp[1].strip())

        if block == "IMAGE_HEADER":
            if line.find("BYTES") != -1 and not(line.startswith("/*")):
                tmp = line.split("=")
                BYTES = int(tmp[1].strip())

        if block == "ROVER_COORDINATE_SYSTEM":
            if line.find("ORIGIN_OFFSET_VECTOR") != -1 and not(line.startswith("/*")):
                tmp = line.split("=")
                ORIGIN_OFFSET_VECTOR = str(tmp[1].strip())

                fline = re.sub('[(!@#$)]', '', ORIGIN_OFFSET_VECTOR)
                pf = fline.strip().split(",")

                bRoverVec[:] = float(pf[1]), float(pf[0]), -float(pf[2])

    f.close

    # Open the img label file (binary data part)
    try:
        if FileAndExt[1].isupper():
            f2 = open(FileAndExt[0] + ".IMG", 'rb')
        else:
            f2 = open(FileAndExt[0] + ".img", 'rb')
    except:
        return

    edit = f2.read()
    meh = edit.find(b'LBLSIZE')
    f2.seek(meh + BYTES)

    # Create a list of bands containing an empty list for each band
    bands = []

    # Read data for each band at a time
    for bandnum in range(0, 3):
        bands.append([])

        for linenum in range(0, LINES):

            bands[bandnum].append([])

            for pixnum in range(0, LINE_SAMPLES):

                # Read one data item (pixel) from the data file.
                dataitem = f2.read(4)

                if (dataitem == ""):
                    print ('ERROR, Ran out of data to read before we should have')

                # If everything worked, unpack the binary value and store it in
                # the appropriate pixel value
                bands[bandnum][linenum].append(
                    struct.unpack('>f', dataitem)[0])

    f2.close

    Vertex = []
    Faces = []

    nulvec = Vector((0.0, 0.0, 0.0))

    for j in range(0, LINES):
        for k in range(0, LINE_SAMPLES):
            vec = Vector((float(bands[1][j][k]), float(
                bands[0][j][k]), float(-bands[2][j][k])))
            vec = vec * 0.1
            Vertex.append(vec)

    del bands

    # simple dehole (bridge)
    #max_fill_length = fill_length
    max_fill_length = 0.6
    if(do_fill):
        for j in range(0, LINES - 1):
            for k in range(0, LINE_SAMPLES - 1):
                if Vertex[j * LINE_SAMPLES + k] != nulvec:
                    m = 1
                    while Vertex[(j + m) * LINE_SAMPLES + k] == nulvec and (j + m) < LINES - 1:
                        m = m + 1

                    if m != 1 and Vertex[(j + m) * LINE_SAMPLES + k] != nulvec:
                        VertexA = Vertex[j * LINE_SAMPLES + k]
                        VertexB = Vertex[(j + m) * LINE_SAMPLES + k]
                        sparevec = VertexB - VertexA
                        if sparevec.length < max_fill_length:
                            for n in range(0, m):
                                Vertex[(j + n) * LINE_SAMPLES +
                                       k] = VertexA + (sparevec / m) * n

    for j in range(0, LINES - 1):
        for k in range(0, LINE_SAMPLES - 1):
            Faces.append(((j * LINE_SAMPLES + k), (j * LINE_SAMPLES + k + 1),
                          ((j + 1) * LINE_SAMPLES + k + 1), ((j + 1) * LINE_SAMPLES + k)))

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
                'Tex-' + os.path.basename(FileAndExt[0]), type='IMAGE')
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
            matname = 'Mat-' + os.path.basename(FileAndExt[0])
            the_mat = bpy.data.materials.new(matname)
            the_mat.use_shadeless = True

            mtex = the_mat.texture_slots.add()
            mtex.texture = cTex
            mtex.texture.extension = 'CLIP'
            mtex.texture_coords = 'UV'

            if do_rad:
                # add nodes to clip 16bit luminance roi
                the_mat.use_nodes = True

                tree = the_mat.node_tree
                nodes = tree.nodes
                links = tree.links

                matnode = nodes.get("Material")
                matnode.material = the_mat
                matnode.location = 0, 200
                matnode.name = matname

                outnode = nodes.get("Output")
                outnode.location = 500, 200

                curvenode = nodes.new('ShaderNodeRGBCurve')
                curvenode.location = 200, 200

                links.new(curvenode.outputs[0], outnode.inputs[0])
                links.new(matnode.outputs[0], curvenode.inputs[1])

                curvenode.mapping.curves[3].points[0].location.x = curve_minval
                curvenode.mapping.curves[3].points[0].location.y = 0.0
                curvenode.mapping.curves[3].points[1].location.x = curve_maxval
                curvenode.mapping.curves[3].points[1].location.y = 1.0
                curvenode.mapping.update()

                outnode.location = 500, 200
                links.new(curvenode.outputs[0], outnode.inputs[0])
                links.new(matnode.outputs[0], curvenode.inputs[1])

            # add material to object
            obj.data.materials.append(the_mat)
    except IOError:
        print('Oh dear. Missing %s' % (imgfilename))

    uvteller = 0

    # per face !
    for j in range(0, LINES - 1):
        for k in range(0, LINE_SAMPLES - 1):
            tc1 = Vector(((1.0 / LINE_SAMPLES) * k, 1.0 - (1.0 / LINES) * j))
            tc2 = Vector(((1.0 / LINE_SAMPLES) * (k + 1),
                          1.0 - (1.0 / LINES) * j))
            tc3 = Vector(((1.0 / LINE_SAMPLES) * (k + 1),
                          1.0 - (1.0 / LINES) * (j + 1)))
            tc4 = Vector(((1.0 / LINE_SAMPLES) * k,
                          1.0 - (1.0 / LINES) * (j + 1)))

            bpy.data.objects[TARGET_NAME].data.uv_layers[
                0].data[uvteller].uv = tc1
            uvteller = uvteller + 1
            bpy.data.objects[TARGET_NAME].data.uv_layers[
                0].data[uvteller].uv = tc2
            uvteller = uvteller + 1
            bpy.data.objects[TARGET_NAME].data.uv_layers[
                0].data[uvteller].uv = tc3
            uvteller = uvteller + 1
            bpy.data.objects[TARGET_NAME].data.uv_layers[
                0].data[uvteller].uv = tc4
            uvteller = uvteller + 1

    # remove verts lacking xyz data
    bpy.ops.object.mode_set(mode='EDIT')
    mesh_ob = bpy.context.object
    me = mesh_ob.data
    bm = bmesh.from_edit_mesh(me)

    verts = [v for v in bm.verts if v.co[0] ==
             0.0 and v.co[1] == 0.0 and v.co[2] == 0.0]
    bmesh.ops.delete(bm, geom=verts, context=1)
    bmesh.update_edit_mesh(me)

    # remove redundant verts
    bpy.ops.object.mode_set(mode='EDIT')
    mesh_ob = bpy.context.object
    me = mesh_ob.data
    bm = bmesh.from_edit_mesh(me)

    verts = [v for v in bm.verts if len(v.link_faces) == 0]
    bmesh.ops.delete(bm, geom=verts, context=1)
    bmesh.update_edit_mesh(me)

    bpy.ops.object.editmode_toggle()

    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')
    bpy.ops.object.mode_set(mode='OBJECT')

    # mesh generation is done here, adding camera and text follows

    cam = bpy.data.cameras.new('Camera')
    cam_ob = bpy.data.objects.new(
        'Cam-' + os.path.basename(FileAndExt[0]), cam)

    bRoverVec = bRoverVec * 0.1

    mat_loc = mathutils.Matrix.Translation(bRoverVec)
    mat_trans = mathutils.Matrix.Translation((0.0, 0.0, 0.15))

    cam_ob.matrix_world = mat_loc * mat_trans

    # Create Credit text
    trover = ['Spirit', 'Opportunity', 'Curiosity']

    if creation_date.startswith('\"'):
        date_object = datetime.strptime(
            creation_date[1:23], '%Y-%m-%dT%H:%M:%S.%f')
    else:
        date_object = datetime.strptime(
            creation_date[0:22], '%Y-%m-%dT%H:%M:%S.%f')

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

    tagtext = trover[rover - 1] + ' ' + whichcam + ' Navcam Image at Sol ' + str(sol) + '\n' + str(
        date_object.strftime('%d %b %Y %H:%M:%S')) + ' UTC\nNASA / JPL-CALTECH / phaseIV'

    bpy.ops.object.text_add(enter_editmode=True,
                            location=(-0.02, -0.0185, -0.05))
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

    expoint = obj.matrix_world.to_translation(
    ) + Vector((0.0, 0.0, -0.04 - distvec.length * 0.1))
    look_at(cam_ob, expoint)

    bpy.context.scene.objects.link(cam_ob)
    bpy.context.scene.camera = cam_ob
    bpy.context.scene.update()

    cam.clip_start = 0.01
    cam.draw_size = 0.1

    print ('mesh generation complete.')
    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)


def look_at(obj_camera, point):
    loc_camera = obj_camera.matrix_world.to_translation()

    direction = point - loc_camera

    rot_quat = direction.to_track_quat('-Z', 'Y')
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
    self.layout.operator(NavcamDialogOperator.bl_idname,
                         text="Mars Rover NAVCAM Import")


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
