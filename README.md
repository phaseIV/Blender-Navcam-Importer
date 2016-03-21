# Blender-Navcam-Importer
Addon for Blender that creates Martian surfaces from Mars Rover NAVCAM images.

![Curiosity Sol 1051](http://i.imgur.com/DhUrzPi.jpg)

## Instructions
Download the python script and install as addon in Blender’s Preference panel. Enable it.
Select the addon from the Import Menu (File > Import) or from the Misc tab in the Tools menu.

## How?
It works fairly simple, enter or paste the name of a valid Left Navcam image (with or without extension) in the popup dialog and press OK.
The addon will automatically download the corresponding depth and image products from PDS/NASA and stitches the data together into a single UV textured mesh.
Then it will add a caption, set a camera and adjust the scene so Blender can render the scene immediately.
  
Note that this process takes a while and Blender is unresponsive during execution. The status of the addon can be checked in the terminal window.

![Collection](http://i.imgur.com/gkcLyFg.jpg)

The resulting mesh, which is in no way scientifically accurate, can contain over a million vertices and will have gaps and glitches. For artistic purposes this addon provides an option to fill small gaps.


## Notes
The addon caches all downloaded data in Blender’s Temp directory. Texture images will get packed in the Blend file.

Batch import works by pasting a single line with comma seperated image names into the addon popupmenu.

Mars Rover Navcam images are grayscale only. Projecting color images might get implemented in the future.

Recent Navcam image ID’s don’t work because the depth images are not yet available in PDS.  
Check the following links for Navcam/Sol PDS release schedules:  
MSL: http://pds-geosciences.wustl.edu/missions/msl/  
MER: http://pds-geosciences.wustl.edu/missions/mer/  

Credits: NASA/JPL-CALTECH

![Curiosity Sol 440](http://i.imgur.com/efAPdt2.jpg)
