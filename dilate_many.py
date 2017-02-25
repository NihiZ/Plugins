#!/usr/bin/env python
# logs msg to the error console --> pdb.gimp_message(msg)

### LAYER methods
# Copy active layer to new layer object --> newLayer = pdb.gimp_layer_new_from_drawable(drawable, dest_image)
# Get active layer --> activeLayer = pdb.gimp_image_get_active_layer(image)
# Translate passed layer --> pdb.gimp_layer_translate(layer, xOffset, yOffset)
# merge visible layers (but first hide the base layer, so this stays untouched
# merge layer with next visible --> layer = pdb.gimp_image_merge_down(image, merge_layer, merge_type)
# instantiate new layer --> layer = pdb.gimp_layer_new(image, width, height, type, name, opacity, mode) type = RGB, RGBA, GREY... mode = blending mode
# insert layer --> pdb.gimp_image_insert_layer(image, layer, parent, position)

### General methods
# pdb.gimp_image_undo_group_start(image)
# pdb.gimp_image_undo_group_end(image)

from gimpfu import *

def dilate_many(image, drawable, bg_color, amount_px):

    pdb.gimp_image_undo_group_start(image)

    active_layer = drawable

    # resize layer to image size (must be done for plug-in to work correctly)
    pdb.gimp_layer_resize_to_image_size(active_layer)

    #duplicate alpha channel to channel "Alpha Backup"
    alpha_backup = pdb.gimp_channel_new_from_component(image, 5, "Alpha Backup")
    pdb.gimp_image_insert_channel(image, alpha_backup, None, 0)

    #create a dopy of the current image and the alpha channel
    orig_drawable = pdb.gimp_edit_named_copy(drawable, "orig_drawable")

    for i in range(0, int(amount_px)):
        active_layer = dilate_once(image, active_layer)

    # here, we are now left with one single layer

    # add a layer on the bottom of the stack and fill it with desired backgrond color_var
    active_layer = add_bg_fill(image, bg_color)


    # paste original color layer on top
    floating_selection = pdb.gimp_edit_named_paste(active_layer, orig_drawable, True)
    # floating selection to layer
    pdb.gimp_floating_sel_to_layer(floating_selection)
    # merge visible
    active_layer = pdb.gimp_image_merge_visible_layers(image, 0)

    # flatten image (to crop to content) and re-add alpha channel
    active_layer = pdb.gimp_image_flatten(image)
    pdb.gimp_layer_add_alpha(active_layer)

    layer_mask = channel_to_layer_mask(image, active_layer, alpha_backup)

    # apply curve on layer mask to approximate original mask (x96 (0.375) , y160 (0.625))
    # select layer mask
    pdb.gimp_layer_set_edit_mask(active_layer, True)

    # apply curve on layer_mask to brighten midtones
    # the gimp 2.9 function gimp_drawable_curves_spline expects NORMALIZED curve values

    #CODE FOR GIMP 2.9
    # gimp_2_9_curve = (0, 0, 0.375, 0.625, 1, 1)
    # pdb.gimp_drawable_curves_spline(layer_mask, 0, 6, gimp_2_9_curve)
    #END CODE FOR GIMP 2.9

    #CODE FOR GIMP 2.8
    gimp_2_8_curve = (0, 0, 96, 160, 255 ,255)
    pdb.gimp_curves_spline(layer_mask, 0, 6, gimp_2_8_curve)
    #END CODE FOR GIMP 2.8


    pdb.gimp_image_undo_group_end(image)

register(
    "python-fu-dilate_many",
    "Dilates and merges selected layer by user defined amount of pixels",
    "Dilates and merges selected layer and adds background color according to user input.\
    \nThis is to prevent colorbleeding on semi transparent pixels (especially visible when using mip maps in Game-Engines)",
    "Nihi", "Nihi", "2017",
    "Dilate Many...",
    "RGBA", # Mandatory image type: *, RGB, RGBA, RGB*, GRAY
    [
        (PF_IMAGE, "image", "takes current image", None),
        (PF_DRAWABLE, "drawable", "Input layer", None),
        (PF_COLOR, "bg_color", "Background Color\nHint: You have to\nClick and Drag after\nselecting the eyedropper", (1.0, 1.0, 1.0)),
        (PF_SLIDER, "amount_px", "Dilate by (px):", 8, (1, 16, 1)),
    ],
    [],
    dilate_many,
    menu="<Image>/Filters/Generic")



# helper methods

def channel_to_layer_mask(image, active_layer, channel):
    """Sets channel layer mask on active_layer and returns reference to the mask (type = channel)"""
    # set active channel
    gimp.pdb.gimp_image_set_active_channel(image, channel)
    # create mask from active channel
    mask = pdb.gimp_layer_create_mask(active_layer, 6)
    # add active channel as layer mask
    gimp.pdb.gimp_layer_add_mask(active_layer,mask)

    return mask

def add_bg_fill(image, bg_color):
    "Fills transparent pixels with the specified bg color. Returns merged result"
    #create new layer and insert into image
    bg_layer = pdb.gimp_layer_new(image, image.width, image.height, 0, "bg", 100, 0)
    pdb.gimp_image_insert_layer(image, bg_layer, None, 1)

    #change foreground color and fill bg_layer
    pdb.gimp_context_set_foreground(bg_color)
    pdb.gimp_edit_bucket_fill(bg_layer, 0, 0, 100, 255, False, 1, 1)

    # merge visible again
    active_layer = pdb.gimp_image_merge_visible_layers(image, 0)
    return active_layer

def dilate_once(image, active_layer):
    """Creates 4 duplicates of the active, offsets them by one pixel in every direction. A merged result is returned as the active_layer"""

    # first of all find out how many layers there are at the moment so we can set the correct insert position for our duplicates
    num_existing_layers = len(image.layers)

    #1. Duplicate active layer and insert into image
    duplicate_layer(image, active_layer, True, num_existing_layers)

    #2. Move active layer by y0 x minus1
    active_layer = move_layer(image, 0, 1)

    # 3. Make sure new layer is below original layer (move down on layer stack)
    # this is assured inside --> pdb.gimp_image_insert_layer()

    # 4. Duplicate the moved layer (which is the active layer)
    duplicate_layer(image, active_layer, False, num_existing_layers)

    # 5. move the new duplicate y1 x1
    active_layer = move_layer(image, 1, -1)

    # 6. Duplicate last moved copy
    duplicate_layer(image, active_layer, False, num_existing_layers)

    # 7. Move it y minus 1 x1
    active_layer = move_layer(image, -1, -1)

    # 8. Duplicate latest copy
    duplicate_layer(image, active_layer, False, num_existing_layers)

    # 9. Move y minus1 x minus1
    active_layer = move_layer(image, -1, 1)

    # 10 Merge visible
    active_layer = pdb.gimp_image_merge_visible_layers(image, 0)

    return active_layer


def duplicate_layer(image, active_layer, initial_call, num_existing_layers):
    """duplicates acitve_layer and inserts it on the correct positions in the layer stack"""
    insert_index = None;

    if(initial_call == True):
        insert_index = len(image.layers)
    else:
        #pdb.gimp_message(num_existing_layers)
        insert_index = num_existing_layers

    dupli_layer = pdb.gimp_layer_new_from_drawable(active_layer, image)
    pdb.gimp_image_insert_layer(image, dupli_layer, None, insert_index)

def move_layer(image, x, y):
    """moves currently active layer by x & y offset and returns the active layer"""
    active_layer = pdb.gimp_image_get_active_layer(image)
    pdb.gimp_layer_translate(active_layer, x, y)
    return active_layer

main()
