"""Read-only offline access to a local Forever CASC using the CascLib DLL."""
import ctypes
from pathlib import Path


class _OpenArgs(ctypes.Structure):
    _fields_ = [('size', ctypes.c_size_t), ('local_path', ctypes.c_char_p),
                ('code_name', ctypes.c_char_p), ('region', ctypes.c_char_p),
                ('progress_callback', ctypes.c_void_p), ('progress_param', ctypes.c_void_p),
                ('product_callback', ctypes.c_void_p), ('product_param', ctypes.c_void_p),
                ('locale_mask', ctypes.c_uint32), ('flags', ctypes.c_uint32),
                ('build_key', ctypes.c_char_p), ('cdn_host', ctypes.c_char_p)]


class _OpenArgsWide(ctypes.Structure):
    _fields_ = [(name, ctypes.c_wchar_p if kind is ctypes.c_char_p else kind)
                for name, kind in _OpenArgs._fields_]


class ForeverCasc:
    """Open a user-supplied game store locally; never request network access."""
    def __init__(self, library, data_directory, *, wide=False):
        if not hasattr(ctypes, 'WinDLL'):
            raise OSError('CascLib Windows requis.')
        self.library = ctypes.WinDLL(str(Path(library).resolve(strict=True)), use_last_error=True)
        lib = self.library
        args_type = _OpenArgsWide if wide else _OpenArgs
        text_type = ctypes.c_wchar_p if wide else ctypes.c_char_p
        lib.CascOpenStorageEx.argtypes = [text_type, ctypes.POINTER(args_type), ctypes.c_bool,
                                         ctypes.POINTER(ctypes.c_void_p)]
        lib.CascOpenStorageEx.restype = ctypes.c_bool
        lib.CascCloseStorage.argtypes = [ctypes.c_void_p]
        lib.CascCloseStorage.restype = ctypes.c_bool
        lib.CascOpenFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                                     ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
        lib.CascOpenFile.restype = ctypes.c_bool
        lib.CascGetFileSize64.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64)]
        lib.CascGetFileSize64.restype = ctypes.c_bool
        lib.CascReadFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                                     ctypes.POINTER(ctypes.c_uint32)]
        lib.CascReadFile.restype = ctypes.c_bool
        lib.CascCloseFile.argtypes = [ctypes.c_void_p]
        lib.CascCloseFile.restype = ctypes.c_bool
        data = str(Path(data_directory).resolve(strict=True))
        if not wide:
            try:
                data = data.encode('mbcs', errors='strict')
            except UnicodeEncodeError as error:
                raise ValueError('Le lecteur CASC actuel ne prend pas en charge ce chemin Unicode.') from error
        args = args_type()
        args.size = ctypes.sizeof(args)
        args.code_name, args.region = ('wowf', 'us') if wide else (b'wowf', b'us')
        args.locale_mask = 0xffffffff
        self.handle = ctypes.c_void_p()
        if not lib.CascOpenStorageEx(data, ctypes.byref(args), False, ctypes.byref(self.handle)):
            raise OSError(ctypes.get_last_error(), 'Ouverture du stockage Forever impossible.')

    def read(self, ident):
        if not self.handle:
            raise ValueError('Stockage fermé.')
        if type(ident) is not int or not 1 <= ident <= 0xffffffff:
            raise ValueError('Identifiant de texture invalide.')
        handle = ctypes.c_void_p()
        name = ctypes.create_string_buffer(('FILE%08X.dat' % ident).encode('ascii'))
        if not self.library.CascOpenFile(self.handle, ctypes.cast(name, ctypes.c_void_p), 0, 0,
                                         ctypes.byref(handle)):
            code = ctypes.get_last_error()
            if code in (2, 3):
                raise FileNotFoundError(code, 'Texture CASC introuvable.', str(ident))
            raise OSError(code, 'Ouverture de texture CASC impossible.', str(ident))
        try:
            size = ctypes.c_uint64()
            if not self.library.CascGetFileSize64(handle, ctypes.byref(size)):
                raise OSError(ctypes.get_last_error(), 'Taille CASC illisible.')
            if not 1 <= size.value <= 16777216:
                raise ValueError('Taille de texture CASC invalide.')
            buffer = ctypes.create_string_buffer(size.value)
            read = ctypes.c_uint32()
            if not self.library.CascReadFile(handle, buffer, size.value, ctypes.byref(read)):
                raise OSError(ctypes.get_last_error(), 'Lecture CASC impossible.')
            if read.value != size.value:
                raise OSError('Lecture CASC incomplète.')
            return buffer.raw
        finally:
            self.library.CascCloseFile(handle)

    def close(self):
        if self.handle:
            self.library.CascCloseStorage(self.handle)
            self.handle = ctypes.c_void_p()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
