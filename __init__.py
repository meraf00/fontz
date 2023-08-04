import bpy
import bpy.utils.previews
import addon_utils
import os
import shutil
from . import aligning_tools
import importlib
from mathutils import Euler, Vector

importlib.reload(aligning_tools)

bl_info = {
    "name": "fontz",
    "author": "Leul Wujira",
    "location": "View3D > Tools Panel /Properties panel",
    "version": (0, 0, 1),
    "blender": (2, 80, 0),
    "description": "3D font style generator",
    "category": "3D View"
}


class GenerateStyle(bpy.types.Operator):
    """Operator that generates the 3D characters"""

    bl_idname = 'object.generate_style'
    bl_label = 'Generate text with 3D font style'

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Reads user typed text, selects letter models from selected font and place them in viewport"""

        # the folder where all font files are stored
        prefab_dir = os.path.join(os.path.split(os.path.realpath(__file__))[
                                  0], "styles")

        # get user selected font
        font_name = context.scene.styled_font

        # font files are named with this convension: <font name>.blend
        file_path = os.path.join(prefab_dir, f'{font_name}.blend')

        # get what the user inputed
        text = context.scene.styled_text
        letters = set(text)

        if not os.path.exists(file_path):
            return {"FINISHED"}

        # load only letters found in text for performance
        with bpy.data.libraries.load(file_path) as (data_from, data_to):
            data_to.objects = []

            # go through the letters we need to load
            for letter in letters:
                # case 1 - already loaded
                if bpy.data.objects.get(f'{letter}-{font_name}'):
                    continue

                # case 2 - not loaded yet
                # find the letter object and load it
                for object_name in data_from.objects:
                    if object_name == f'{letter}-{font_name}':
                        data_to.objects.append(object_name)
                        break

        # collection to house letters
        word = bpy.data.collections.new(text)

        # Add collection to scene collection
        bpy.context.scene.collection.children.link(word)

        spacing = context.scene.spacing
        pos = 0
        # for each letter in text we first copy loaded object
        # then place it next to last letter
        # obj - is the original character model loaded from font file
        # pos - keeps track of x-axis position of letter
        for letter in text:
            obj = bpy.data.objects.get(f'{letter}-{font_name}')
            if obj:
                new_obj = obj.copy()
                new_obj.data = obj.data.copy()
                new_obj.location = (0, 0, 0)

                word.objects.link(new_obj)
                bpy.ops.object.select_all(action='DESELECT')
                new_obj.select_set(True)
                bpy.ops.transform.translate(value=(pos, 0, 0))
                pos += new_obj.dimensions.x + spacing

        return {"FINISHED"}

    @classmethod
    def register(cls):
        """Called when blender registers the add-on. Registers blender properties that will 
        be used in text generation.

        styled_font - the name of selected font
        styled_text - the user inputed text
        spacing - amount of spacing between letters
        """
        fonts = []

        i = 1
        for k, v in sorted(previews.items()):
            fonts.append((k, k.capitalize(), 'Font name', "", i))
            i += 1

        bpy.types.Scene.styled_font = bpy.props.EnumProperty(
            items=fonts, name='Choose Font'
        )

        bpy.types.Scene.styled_text = bpy.props.StringProperty(
            name="Text",
            description="Input text")

        def distribute(self, context):
            collection = context.selected_objects[0].users_collection
            if not len(collection):
                return

            objects = collection[0].all_objects
            if not len(objects):
                return

            spacing = context.scene.spacing

            init_pos = objects[0].location
            final_pos = objects[-1].location

            direction = (Vector(final_pos) -
                         Vector(init_pos))
            direction.normalize()
            direction = spacing * direction
            for pos, obj in enumerate(objects):
                obj.location = init_pos + pos * direction
                # bpy.ops.transform.translate(value=direction)

        bpy.types.Scene.spacing = bpy.props.FloatProperty(
            name="Spacing",
            description="Letter spacing",
            default=0.5,
            min=0.5,
            max=10.0,
            precision=2,
            update=distribute)

    @classmethod
    def unregister(cls):
        """Remove registered properties."""
        del bpy.context.scene.styled_text
        del bpy.context.scene.styled_font
        del bpy.context.scene.spacing


class PreprocessFontFile(bpy.types.Operator):
    """Operator to prepare new font files for loading. Renames objects so that our loader finds the letter models."""

    bl_idname = "object.preprocess_fontfile"
    bl_label = "Prepare Font File"
    bl_description = "Modifiy names of objects, prepare file for use as font"

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Looks for objects with single letter name and appends font name"""

        # name of new font
        new_font = context.scene.new_font_name

        if not new_font:
            return {"FINISHED"}

        for obj in bpy.data.objects:
            if len(obj.name) == 1:
                obj.name = f'{obj.name}-{new_font}'

        return {"FINISHED"}

    @classmethod
    def register(cls):
        # the font name to use while renaming objects
        bpy.types.Scene.new_font_name = bpy.props.StringProperty(
            name="Font name",
            description="Name of new font, should be same as file name.")

    @classmethod
    def unregister(cls):
        del bpy.context.scene.new_font_name


class FontRemover(bpy.types.Operator):
    """Deletes fonts"""

    bl_idname = "object.remove_fontfile"
    bl_label = "Delete Font"
    bl_description = "Remove font"

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Deletes the preview and font file specified in delete_font propery."""

        # directory where font files are located
        prefab_dir = os.path.join(os.path.split(os.path.realpath(__file__))[
            0], "styles")

        # directory where font preview images are located
        preview_dir = os.path.join(os.path.split(os.path.realpath(__file__))[
            0], "previews")

        scn = context.scene

        font_file = os.path.join(prefab_dir, f'{scn.delete_font}.blend')

        # find preview file that belongs to the font in the preview folder
        # preview files are named as such:
        # <font name>.ext where ext is any valid image extension
        preview_file = None
        for file in os.listdir(preview_dir):
            if scn.delete_font == os.path.splitext(file)[0]:
                preview_file = os.path.join(preview_dir, file)
                break

        # check if preview file exists and delete both the preview and font file,
        # preview image should exist unless the blender add-on folder is tampered with,
        # in that case we do nothing
        if preview_file:
            try:
                os.remove(preview_file)
                os.remove(font_file)

                # reload script to update our font list
                addon_utils.disable(__name__)
                bpy.ops.script.reload()
                addon_utils.enable(__name__)

            except Exception as e:
                print(e)

        return {"FINISHED"}

    @classmethod
    def register(cls):
        "Register font selector dropdown used for deletion"

        fonts = []

        i = 1
        for k, v in sorted(previews.items()):
            fonts.append((k, k.capitalize(), 'Font name', "", i))
            i += 1

        bpy.types.Scene.delete_font = bpy.props.EnumProperty(
            items=fonts, name='Font name'
        )

    @classmethod
    def unregister(cls):
        del bpy.context.scene.delete_font


class FontFileLoader(bpy.types.Operator):
    """Adds new font to our font list."""

    bl_idname = "object.load_fontfile"
    bl_label = "Load Font File"
    bl_description = "Load font file"

    @classmethod
    def poll(cls, context):
        return True

    def link_font_preview(self, path):
        """Returns zip containing a font file and respective preview image file

        path - the directory path to look for font file and respective preview file
        """

        font = []
        image = []

        for file in os.listdir(path):
            if file.endswith('.blend'):
                font_name = os.path.splitext(file)[0]
                for p in os.listdir(path):
                    if p != file and os.path.splitext(p)[0] == (font_name):
                        font.append(file)
                        image.append(p)
                        break

        return zip(font, image)

    def execute(self, context):
        """Looks for .blend file (font files) in given directory and their respective preview files.
        Adds them to list of available fonts."""

        # the directory containing new fonts and previews
        font_dir = context.scene.font_dir_path

        # check for the existance of font_dir
        if not (os.path.isdir(font_dir)):
            context.scene.loader_message = "Select folder containing fonts and previews"

            return {"FINISHED"}

        # our internal directory used to store all available font files
        prefab_dir = os.path.join(os.path.split(os.path.realpath(__file__))[
            0], "styles")

        # our internal directory used to store all available font preview images
        preview_dir = os.path.join(os.path.split(os.path.realpath(__file__))[
            0], "previews")

        print("?>>>>", [i for i in self.link_font_preview(font_dir)])
        for font_file_name, image_file_name in self.link_font_preview(font_dir):
            # convert the file name to full path
            filepath = os.path.join(font_dir, font_file_name)
            imagepath = os.path.join(font_dir, image_file_name)

            # copy the font files to our prefab directory
            try:
                new_font_path = os.path.join(prefab_dir, font_file_name)

                shutil.copyfile(filepath, new_font_path)
            except Exception as e:
                context.scene.loader_message = str(e)

            # copy the preview file to our preview folder
            try:
                ext = os.path.splitext(imagepath)[1]
                fontname = os.path.splitext(font_file_name)[0]
                image_file_name = fontname + ext
                new_image_path = os.path.join(preview_dir, image_file_name)

                shutil.copyfile(imagepath, new_image_path)
            except Exception as e:
                context.scene.loader_message = str(e)

        context.scene.loader_message = "Fonts added"

        # reload the script to update the font list UI
        try:
            addon_utils.disable(__name__)
            bpy.ops.script.reload()
            addon_utils.enable(__name__)
        except:
            pass
        return {"FINISHED"}

    @classmethod
    def register(cls):
        """Register the blender property that takes user input for font directory and a message property
        used to display message regarding font loading process"""

        bpy.types.Scene.font_dir_path = bpy.props.StringProperty(
            name="Font path",
            description="Preprocessor Message",
            subtype='DIR_PATH')

        # bpy.types.Scene.image_file_path = bpy.props.StringProperty(
        #     name="Image path",
        #     description="Preprocessor Message",
        #     subtype='FILE_PATH')

        bpy.types.Scene.loader_message = bpy.props.StringProperty(
            name="",
            description="Loader Message")

    @classmethod
    def unregister(cls):
        del bpy.context.scene.font_file_path
        # del bpy.context.scene.image_file_path
        del bpy.context.scene.loader_message


class RNAD321_PT_FontPanel(bpy.types.Panel):
    """Font generation UI"""

    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Font Style"
    bl_label = "Generate Text"

    def draw(self, context):
        """Displays text input field, font selector and list of fonts in 3 column grid."""
        scn = context.scene
        lay = self.layout

        lay.prop(scn, 'styled_text')

        row = lay.row()
        row.prop(scn, 'styled_font')

        lay.operator('object.generate_style', text="Generate")

        grid = lay.grid_flow(columns=3, align=True)

        # populate the grid with previews,
        # group the name of font and preview image in single box
        # previews is loaded during registration
        # it contains loaded preview images
        for k, v in sorted(previews.items()):
            box = grid.box()
            box.template_icon(icon_value=v[k].icon_id, scale=4)
            box.label(text=f'{k.capitalize()}', icon_value=v[k].icon_id)

    @classmethod
    def register(cls):
        print('Registered class: %s' % cls.bl_label)

    @classmethod
    def unregister(cls):
        print('Unregistered class: %s' % cls.bl_label)


class RNAD321_PT_PreprocessFontFile(bpy.types.Panel):
    """UI for preprocessing file"""

    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Font Style"
    bl_label = "Prepare Font File"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        lay = self.layout

        lay.prop(context.scene, 'new_font_name')

        lay.operator('object.preprocess_fontfile', text='Prepare File')

        lay.label(text="Font name should be same as blender file name")


class RNAD321_PT_FontFileLoader(bpy.types.Panel):
    """UI for displaying font file loading and removing options."""

    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Font Style"
    bl_label = "Add / Remove Font"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        lay = self.layout

        lay.label(text='Add Font')

        lay.prop(context.scene, 'font_dir_path')
        # lay.prop(context.scene, 'image_file_path')

        lay.operator('object.load_fontfile', text='Add Fonts')

        lay.label(text=context.scene.loader_message)

        lay.separator()

        lay.label(text='Remove Font')

        lay.prop(context.scene, 'delete_font')

        lay.operator('object.remove_fontfile', text='Delete Font')


previews = {}
classes = [GenerateStyle,
           PreprocessFontFile,
           FontFileLoader,
           FontRemover,
           RNAD321_PT_FontPanel,
           aligning_tools.RAND321_OBJECT_OT_align_tools,
           aligning_tools.RAND321VIEW3D_PT_AlignUi,
           RNAD321_PT_PreprocessFontFile,
           RNAD321_PT_FontFileLoader]


def unregister():
    # remove previews
    for pcoll in previews.values():
        try:
            print('removing')
            bpy.utils.previews.remove(pcoll)
            print('removing success')
        except Exception as e:
            print(e)
    previews.clear()

    # unregister classes
    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(e)
    print("%s unregister complete" % bl_info.get('name'))


def register():
    try:
        unregister()
    except Exception as e:
        print(e)

    try:
        # prepare preview
        pcoll = bpy.utils.previews.new()

        # folder that contains all fonts
        prefab_dir = os.path.join(os.path.split(os.path.realpath(__file__))[
                                  0], "styles")

        # folder that contains all preview images
        previews_dir = os.path.join(os.path.split(os.path.realpath(__file__))[
                                    0], "previews")

        preview_files = []
        for file in os.listdir(previews_dir):
            fontname = os.path.splitext(file)[0]
            if f'{fontname}.blend' in os.listdir(prefab_dir):
                preview_files.append(file)

        # load all files to blender preview and store them in preview dictionary for later use
        for fname in preview_files:
            # load image
            pcoll.load(os.path.splitext(fname)[0], os.path.join(
                previews_dir, fname), 'IMAGE')

            # store reference in preview dict
            previews[os.path.splitext(fname)[0]] = pcoll

    except Exception as e:
        print(e)

    # register class
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            print(e)
    print("%s regiteration completed." % bl_info.get('name'))
