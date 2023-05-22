import os
import string
import glob
from sys import platform
from pathlib import Path


class FileSystem:
    defaults = {}

    defaults['ldraw_path'] = ''
    ldraw_path = defaults['ldraw_path']

    defaults['studio_ldraw_path'] = ''
    studio_ldraw_path = defaults['studio_ldraw_path']

    defaults['prefer_studio'] = False
    prefer_studio = defaults['prefer_studio']

    defaults['prefer_unofficial'] = False
    prefer_unofficial = defaults['prefer_unofficial']

    defaults['resolution'] = 'Standard'
    resolution = defaults['resolution']

    search_dirs = []
    lowercase_paths = {}

    @classmethod
    def reset_caches(cls):
        cls.search_dirs = []
        cls.lowercase_paths = {}

    @staticmethod
    def locate_ldraw():
        ldraw_folder_name = 'ldraw'

        # home = os.path.expanduser("~")
        home = str(Path.home())
        ldraw_path = os.path.join(home, ldraw_folder_name)
        if os.path.isdir(ldraw_path):
            return ldraw_path

        if platform == "linux" or platform == "linux2":
            pass
            # linux
        elif platform == "darwin":
            pass
            # OS X
        elif platform == "win32":
            for drive_letter in string.ascii_lowercase:
                ldraw_path = os.path.join(os.path.join(f"{drive_letter}:\\", ldraw_folder_name))
                if os.path.isdir(ldraw_path):
                    return ldraw_path
        return ""

    @staticmethod
    def locate_studio_ldraw():
        ldraw_folder_name = 'ldraw'

        if platform == "linux" or platform == "linux2":
            pass
            # linux
        elif platform == "darwin":
            pass
            # OS X
        elif platform == "win32":
            studio_path = os.path.join(os.environ["ProgramFiles"], 'Studio 2.0', ldraw_folder_name)
            if os.path.isdir(studio_path):
                return studio_path

            studio_path = os.path.join(os.environ["ProgramFiles(x86)"], 'Studio 2.0', ldraw_folder_name)
            if os.path.isdir(studio_path):
                return studio_path

        return ""

    @classmethod
    def build_search_paths(cls, parent_filepath=None):
        cls.reset_caches()

        ldraw_roots = []

        # append top level file's directory
        # https://forums.ldraw.org/thread-24495-post-40577.html#pid40577
        # post discussing path order, this order was chosen
        # except that the current file's dir isn't scanned, only the current dir of the top level file
        # https://forums.ldraw.org/thread-24495-post-45340.html#pid45340
        if parent_filepath is not None:
            ldraw_roots.append(os.path.dirname(parent_filepath))

        if cls.prefer_studio:
            if cls.prefer_unofficial:
                ldraw_roots.append(os.path.join(cls.studio_ldraw_path, "unofficial"))
                ldraw_roots.append(os.path.join(cls.ldraw_path, "unofficial"))
                ldraw_roots.append(os.path.join(cls.studio_ldraw_path))
                ldraw_roots.append(os.path.join(cls.ldraw_path))
            else:
                ldraw_roots.append(os.path.join(cls.studio_ldraw_path))
                ldraw_roots.append(os.path.join(cls.ldraw_path))
                ldraw_roots.append(os.path.join(cls.studio_ldraw_path, "unofficial"))
                ldraw_roots.append(os.path.join(cls.ldraw_path, "unofficial"))
        else:
            if cls.prefer_unofficial:
                ldraw_roots.append(os.path.join(cls.ldraw_path, "unofficial"))
                ldraw_roots.append(os.path.join(cls.studio_ldraw_path, "unofficial"))
                ldraw_roots.append(os.path.join(cls.ldraw_path))
                ldraw_roots.append(os.path.join(cls.studio_ldraw_path))
            else:
                ldraw_roots.append(os.path.join(cls.ldraw_path))
                ldraw_roots.append(os.path.join(cls.studio_ldraw_path))
                ldraw_roots.append(os.path.join(cls.ldraw_path, "unofficial"))
                ldraw_roots.append(os.path.join(cls.studio_ldraw_path, "unofficial"))

        for root in ldraw_roots:
            path = root
            cls.append_search_path(path, root=True)

            path = os.path.join(root, "p")
            cls.append_search_path(path)

            if cls.resolution == "High":
                path = os.path.join(root, "p", "48")
                cls.append_search_path(path)
            elif cls.resolution == "Low":
                path = os.path.join(root, "p", "8")
                cls.append_search_path(path)

            path = os.path.join(root, "parts")
            cls.append_search_path(path)

            path = os.path.join(root, "parts", "textures")
            cls.append_search_path(path)

            path = os.path.join(root, "models")
            cls.append_search_path(path)

    # build a list of folders to search for parts
    # build a map of lowercase to actual filenames
    @classmethod
    def append_search_path(cls, path, root=False):
        cls.search_dirs.append(path)
        cls.append_lowercase_paths(path, '*')
        if root:
            return
        cls.append_lowercase_paths(path, '**/*')

    @classmethod
    def append_lowercase_paths(cls, path, pattern):
        files = glob.glob(os.path.join(path, pattern))
        for file in files:
            cls.lowercase_paths.setdefault(file.lower(), file)

    @classmethod
    def locate(cls, filename):
        part_path = filename.replace("\\", os.path.sep).replace("/", os.path.sep)
        part_path = os.path.expanduser(part_path)

        # full path was specified
        if os.path.isfile(part_path):
            return part_path

        for dir in cls.search_dirs:
            full_path = os.path.join(dir, part_path)
            full_path = cls.lowercase_paths.get(full_path.lower()) or full_path
            if os.path.isfile(full_path):
                return full_path

        # TODO: requests retrieve missing items from ldraw.org

        print(f"missing {filename}")
        return None
