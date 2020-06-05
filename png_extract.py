import argparse
import os
import re
import zlib


FILE_READ_BUFFER_SIZE = 1024
PNG_SIGNATURE_BYTES = b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a'
PNG_SIGNATURE_RE = re.compile(PNG_SIGNATURE_BYTES)


class ChunkCRCException(Exception):
    pass


class Chunk:
    def __init__(self, _type, data, crc):
        self.type = _type
        self.data = data
        self.crc = crc

    @property
    def body(self):
        return len(self.data).to_bytes(4, 'big') + self.type + self.data + self.crc

    @classmethod
    def from_file(cls, bytes_file, reset_pos=False):
        origin_pos = bytes_file.tell()
        try:
            chunk_data_length = bytes_file.read(4)
            chunk_data_length_int = int.from_bytes(chunk_data_length, 'big')
            chunk_type = bytes_file.read(4)
            chunk_data = bytes_file.read(chunk_data_length_int)
            chunk_crc = bytes_file.read(4)

            if chunk_crc and zlib.crc32(chunk_type + chunk_data) & 0xffffffff == int.from_bytes(chunk_crc, 'big'):
                pass
            else:
                raise ChunkCRCException('CRC check not pass')
            klass = CHUNK_CLASSES_DICT.get(chunk_type, cls)
            return klass(chunk_type, chunk_data, chunk_crc)
        finally:
            if reset_pos:
                bytes_file.seek(origin_pos, 0)

    def __repr__(self):
        return "{} {}".format(self.type, len(self.data))


class IHDR(Chunk):
    pass


class IDAT(Chunk):
    pass


class IEND(Chunk):
    pass


CHUNK_CLASSES_DICT = {
    b'IHDR': IHDR,
    b'IDAT': IDAT,
    b'IEND': IEND
}


def extract_png(bytes_file, start_position, save_to_file=None):
    bytes_file.seek(start_position, 0)
    png_signature = bytes_file.read(len(PNG_SIGNATURE_BYTES))
    if png_signature != PNG_SIGNATURE_BYTES:
        print('Wrong signature in position {}'.format(start_position))
        return

    chunk = Chunk.from_file(bytes_file)
    chunks = [chunk]
    while not isinstance(chunk, IEND):
        chunk = Chunk.from_file(bytes_file)
        chunks.append(chunk)
    if save_to_file:
        with open(save_to_file, 'wb') as new_file:
            new_file.write(png_signature)
            for chunk in chunks:
                new_file.write(chunk.body)


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('file', type=str)
    arg_parser.add_argument('-o', '--out-dir', default='out', required=False)
    arg_parser.add_argument('-p', '--prefix', default='png', required=False)
    args = arg_parser.parse_args()
    in_file = args.file
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)
    png_file_prefix = args.prefix
    png_file_number = 0
    print(in_file, out_dir)
    file_pos = 0
    with open(in_file, 'rb') as bytes_file:
        file_buf = new_bytes = bytes_file.read(FILE_READ_BUFFER_SIZE)
        file_pos += len(new_bytes)
        while new_bytes:
            for m in PNG_SIGNATURE_RE.finditer(file_buf):
                # operate from position of start_png
                buf_start_png_pos = m.span()[0]
                file_start_png_pos = file_pos + buf_start_png_pos - len(file_buf)
                new_png_file_name = os.path.join(out_dir, '{}_{}.png'.format(png_file_prefix, png_file_number))
                while os.path.isfile(new_png_file_name):
                    new_png_file_name = os.path.join(out_dir, '{}_{}.png'.format(png_file_prefix, png_file_number))
                    png_file_number += 1
                print('Extract PNG to {}'.format(new_png_file_name))
                try:
                    extract_png(bytes_file, file_start_png_pos, save_to_file=new_png_file_name)
                    png_file_number += 1
                except ChunkCRCException as crc_error:
                    print(crc_error)
                if bytes_file.tell() != file_pos:
                    bytes_file.seek(file_pos, 0)
            new_bytes = bytes_file.read(FILE_READ_BUFFER_SIZE)
            file_buf = file_buf[-len(PNG_SIGNATURE_BYTES):] + new_bytes
            file_pos += len(new_bytes)


if __name__ == '__main__':
    main()
