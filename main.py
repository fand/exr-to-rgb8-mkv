#!/usr/bin/env python3
import sys
import os
import glob
import subprocess
import struct

try:
    import OpenEXR
    import Imath
    import numpy as np
except ImportError:
    print("Please install required libraries: pip install OpenEXR Imath numpy")
    sys.exit(1)


def exr_to_rgba8_bytes(exr_path, channel_name='Z'):
    """
    Reads the specified EXR file (assuming a single 32-bit float channel)
    and packs it into a 4-byte (R/G/B/A) binary (RGBA8) array.
    Specify the channel_name (e.g., 'Z') for the channel to load.
    """
    exr_file = OpenEXR.InputFile(exr_path)
    dw = exr_file.header()['dataWindow']
    width = dw.max.x - dw.min.x + 1
    height = dw.max.y - dw.min.y + 1

    # Load 32-bit float pixels
    pt = Imath.PixelType(Imath.PixelType.FLOAT)
    # To check if a channel exists, you can examine the list with exr_file.header()['channels'].keys()
    depth_str = exr_file.channel(channel_name, pt)
    # Convert the byte string to a float32 array
    depth_arr = np.frombuffer(depth_str, dtype=np.float32)
    depth_arr = depth_arr.reshape((height, width))

    # Allocate an RGBA8 buffer (height, width, 4)
    rgba = np.zeros((height, width, 4), dtype=np.uint8)

    # Split the float value into 4 bytes and assign them to each RGBA channel
    # (here we use little-endian as an example)
    for y in range(height):
        for x in range(width):
            fval = depth_arr[y, x]
            b = struct.pack('<f', fval)  # float -> 4 bytes (little-endian)
            rgba[y, x, 0] = b[0]  # R
            rgba[y, x, 1] = b[1]  # G
            rgba[y, x, 2] = b[2]  # B
            rgba[y, x, 3] = b[3]  # A

    return rgba.tobytes(), width, height


def main():
    if len(sys.argv) < 2:
        print("Usage: {} <directory_of_exr_files> [<channel_name>]".format(
            sys.argv[0]))
        sys.exit(1)

    exr_dir = sys.argv[1]
    channel_name = sys.argv[2] if len(sys.argv) > 2 else 'Z'

    if not os.path.isdir(exr_dir):
        print(f"Error: {exr_dir} is not a directory.")
        sys.exit(1)

    # Retrieve and sort .exr files in the directory
    exr_list = sorted(glob.glob(os.path.join(exr_dir, '*.exr')))
    if not exr_list:
        print(f"No EXR files found in {exr_dir}.")
        sys.exit(1)

    # Read the first image to get its width and height
    first_rgba, w, h = exr_to_rgba8_bytes(
        exr_list[0], channel_name=channel_name)

    # FFmpeg command: input raw RGBA via pipe and save as FFV1 (lossless) in output.mkv
    ffmpeg_cmd = [
        'ffmpeg',
        '-y',
        '-f', 'rawvideo',
        '-pix_fmt', 'rgba',
        '-s', f'{w}x{h}',
        '-r', '30',                    # Frame rate is arbitrary, can be changed
        '-i', 'pipe:0',
        '-c:v', 'ffv1',
        '-level', '3',
        'output.mkv'
    ]

    print("Running FFmpeg command:")
    print(" ".join(ffmpeg_cmd))

    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    # Write the first frame
    proc.stdin.write(first_rgba)

    # Write subsequent frames
    for exr_path in exr_list[1:]:
        rgba_bytes, w2, h2 = exr_to_rgba8_bytes(
            exr_path, channel_name=channel_name)
        if w2 != w or h2 != h:
            print(
                f"Size mismatch at {exr_path} (expected {w}x{h}, got {w2}x{h2})")
            proc.stdin.close()
            proc.terminate()
            sys.exit(1)
        proc.stdin.write(rgba_bytes)

    # Close the input and wait for the process to finish
    proc.stdin.close()
    proc.wait()

    # Display completion message
    print("Done. Encoded video saved as 'output.mkv'.")


if __name__ == '__main__':
    main()
