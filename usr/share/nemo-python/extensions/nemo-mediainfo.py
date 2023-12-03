import os
from gi.repository import GObject, Gio, Gtk, Nemo
import urllib.parse
import pymediainfo
try:
    import exifread
except Exception:
    exifread = None

GUI = """
<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <requires lib="gtk+" version="3.24"/>
    <object class="GtkScrolledWindow" id="builder_root_widget">
    <property name="visible">True</property>
    <property name="can-focus">True</property>
    <property name="shadow-type">in</property>
    <child>
        <object class="GtkViewport">
        <property name="visible">True</property>
        <property name="can-focus">False</property>
        <child>
            <object class="GtkTreeView" id="treev">
            <property name="visible">True</property>
            <property name="can-focus">True</property>
            <child internal-child="selection">
                <object class="GtkTreeSelection"/>
            </child>
            </object>
        </child>
        </object>
    </child>
    </object>
</interface>
"""

TIME_DURATION_UNITS = (
    ('week', 60*60*24*7),
    ('day', 60*60*24),
    ('hour', 60*60),
    ('min', 60),
    ('sec', 1)
)


def human_time_duration(seconds):
    if seconds == 0:
        return 'inf'
    parts = []
    for unit, div in TIME_DURATION_UNITS:
        amount, seconds = divmod(int(seconds), div)
        if amount > 0:
            parts.append('{} {}{}'.format(amount, unit, "" if amount == 1 else "s"))
    return ', '.join(parts)


class MediaFile():
    filename = ""
    shortname = ""
    tracks = []
    def __init__(self):
        self.tracks = []
        self.filename = ""
        self.shortname = ""

class MediaFileTrack():
    name = ""
    properties = []
    def __init__(self,name):
        self.name = name
        self.properties = []
    def append(self,name,value):
        if value == None:
            return
        self.properties.append(MediaFileTrackProperty(name,value))

class MediaFileTrackProperty():
    name = ""
    value = ""
    def __init__(self,name,value):
        self.name = name
        self.value = value


class MediaPropertyPage(GObject.GObject, Nemo.PropertyPageProvider, Nemo.NameAndDescProvider):
    def get_property_pages(self, files):
        actual_files = []
        for i in files:
            if i.get_uri_scheme() != 'file':
                continue
            if i.is_directory():
                continue

            filename = urllib.parse.unquote(i.get_uri()[7:])
            mediainfo = pymediainfo.MediaInfo.parse(filename)
            mediafile = MediaFile()
            mediafile.filename = filename
            mediafile.shortname = os.path.basename(filename)
            if len(mediafile.shortname) > 30:
                mediafile.shortname = mediafile.shortname[:30] + "..."
            for track in mediainfo.tracks:
                if track.track_type == "Video":
                    mediatrack = MediaFileTrack("Video")
                    fps = float(track.frame_rate)
                    if fps.is_integer():
                        fps = int(fps)
                    if track.format_info == None:
                        mediatrack.append("Format",track.format)
                    else:
                        mediatrack.append("Format",track.format + " ("+str(track.format_info)+")")
                    mediatrack.append("Frame Rate",str(fps) + " FPS (" + str(track.frame_rate_mode) + ")")
                    mediatrack.append("Width",str(track.width) + " pixels")
                    mediatrack.append("Height",str(track.height) + " pixels")
                    mediatrack.append("Duration",human_time_duration(track.duration / 1000))
                    mediatrack.append("Bit rate",str(track.bit_rate / 1000) + " kb/s")
                    mediatrack.append("Bit depth",str(track.bit_depth) + " bits")
                    mediatrack.append("Scan type",str(track.scan_type))
                    mediatrack.append("Compression mode",track.compression_mode)
                    mediafile.tracks.append(mediatrack)
                if track.track_type == "Audio":
                    mediatrack = MediaFileTrack("Audio")
                    mediatrack.append("Format",track.format)
                    mediatrack.append("Mode",track.mode)
                    mediatrack.append("Channels",track.channel_s)
                    mediatrack.append("Duration",human_time_duration(track.duration / 1000))
                    mediatrack.append("Sample rate",str(track.sampling_rate / 1000) + " kb/s")
                    mediatrack.append("Bit rate",str(track.bit_rate / 1000) + " kb/s")
                    mediatrack.append("Compression mode",track.compression_mode)
                    mediafile.tracks.append(mediatrack)
                if track.track_type == "Image":
                    mediatrack = MediaFileTrack("Image")
                    mediatrack.append("Format",track.format)
                    mediatrack.append("Width",str(track.width) + " pixels")
                    mediatrack.append("Height",str(track.height) + " pixels")
                    mediatrack.append("Bit depth",str(track.bit_depth) + " bits")
                    mediatrack.append("Color space",track.color_space)
                    mediatrack.append("Color space (ICC)",track.colorspace_icc)
                    mediatrack.append("Compression mode",track.compression_mode)
                    mediafile.tracks.append(mediatrack)
                    if exifread != None:
                        with open(filename,"rb") as f:
                            tags = exifread.process_file(f)
                            if len(tags) > 0:
                                mediatrack.append("Camera Brand",tags.get("Image Make",None))
                                mediatrack.append("Camera Model",tags.get("Image Model",None))
                                mediatrack.append("Date Taken",tags.get("Image DateTime",None))
                                if "EXIF ExposureTime" in tags:
                                    mediatrack.append("Exposure Time",str(tags["EXIF ExposureTime"]) + " sec.")
                                mediatrack.append("Flash Fired",tags.get("EXIF Flash",None))
                                mediatrack.append("Metering Mode",tags.get("EXIF MeteringMode",None))
                                exifmediatrack = MediaFileTrack("Image EXIF Data")
                                for tag in tags.keys():
                                    if tag not in ("JPEGThumbnail", "TIFFThumbnail", "Filename", "EXIF MakerNote", "EXIF UserComment"):
                                        exifmediatrack.append(tag,tags[tag])
                                mediafile.tracks.append(exifmediatrack)
            if len(mediafile.tracks) == 0:
                continue


            actual_files.append(mediafile)
        
        if len(actual_files) == 0:
            return []
        
        self.property_label = Gtk.Label("Media")
        self.property_label.show()
        
        self.builder = Gtk.Builder()
        self.builder.add_from_string(GUI)
        self.treev: Gtk.TreeView = self.builder.get_object("treev")

        self.store = Gtk.TreeStore(str,str)
        self.treev.set_model(self.store)
        for i in actual_files:
            fileparent = None
            if len(actual_files) > 1:
                fileparent = self.store.append(None,[i.shortname,""])
            for mt in i.tracks:
                storetrack: Gtk.TreeIter = self.store.append(fileparent,[mt.name,""])
                for prop in mt.properties:
                    self.store.append(storetrack,[prop.name,str(prop.value)])

        self.treev.expand_all()

        for i, column_title in enumerate(["Property","Value"]):
            if i == 0:
                renderer = Gtk.CellRendererText(weight_set=True,weight=600)
            else:
                renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            column.set_resizable(True)
            self.treev.append_column(column)

        return [
            Nemo.PropertyPage(
                name="NemoPython::media",
                label=self.property_label,
                page=self.builder.get_object("builder_root_widget")
            )
        ]

    def get_name_and_desc(self):
        return [("Nemo Media Tab:::View video/audio/image information from the properties tab in Nemo")]