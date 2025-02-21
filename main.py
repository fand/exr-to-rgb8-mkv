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
    print("Please install the required libraries: pip install OpenEXR Imath numpy")
    sys.exit(1)


def get_exr_min_max(exr_path, channel_name='Z'):
    """
    Reads the specified EXR file and returns the minimum and maximum values
    of the given channel (e.g., 'Z').
    """
    exr_file = OpenEXR.InputFile(exr_path)

    pt = Imath.PixelType(Imath.PixelType.FLOAT)
    depth_str = exr_file.channel(channel_name, pt)
    depth_arr = np.frombuffer(depth_str, dtype=np.float32)

    return float(depth_arr.min()), float(depth_arr.max())


def exr_to_rgba8_bytes_with_global_scale(exr_path, channel_name, global_min, global_max):
    """
    Reads the specified EXR file (channel_name), then normalizes the depth data
    to [0..1] using the provided global_min and global_max.
    After normalization, the function packs the values into RGBA8 by converting
    each float to a 4-byte representation (little endian).
    Returns the packed byte array along with (width, height).
    """
    exr_file = OpenEXR.InputFile(exr_path)
    dw = exr_file.header()['dataWindow']
    width = dw.max.x - dw.min.x + 1
    height = dw.max.y - dw.min.y + 1

    pt = Imath.PixelType(Imath.PixelType.FLOAT)
    depth_str = exr_file.channel(channel_name, pt)
    depth_arr = np.frombuffer(
        depth_str, dtype=np.float32).reshape((height, width))

    # Normalize using global_min/global_max
    if global_max > global_min:
        depth_arr = (depth_arr - global_min) / (global_max - global_min)
    else:
        # If all values are the same across all frames, set them to 0
        depth_arr.fill(0.0)

    # Create an RGBA8 buffer
    rgba = np.zeros((height, width, 4), dtype=np.uint8)

    # Pack each float [0..1] into 4 bytes in little endian order
    for y in range(height):
        for x in range(width):
            fval = depth_arr[y, x]
            b = struct.pack('<f', fval)  # float -> 4 bytes (little endian)
            rgba[y, x, 0] = b[0]  # R
            rgba[y, x, 1] = b[1]  # G
            rgba[y, x, 2] = b[2]  # B
            rgba[y, x, 3] = b[3]  # A

    return rgba.tobytes(), width, height


def main():
    if len(sys.argv) < 3:
        print(
            f"Usage: {sys.argv[0]} <directory_of_exr_files> <output_path> [channel_name]")
        sys.exit(1)

    exr_dir = sys.argv[1]
    output_file = sys.argv[2]
    channel_name = sys.argv[3] if len(sys.argv) > 3 else 'Z'

    if not os.path.isdir(exr_dir):
        print(f"Error: {exr_dir} is not a directory.")
        sys.exit(1)

    # Collect all EXR files in the specified directory
    exr_list = sorted(glob.glob(os.path.join(exr_dir, '*.exr')))
    if not exr_list:
        print(f"No EXR files found in {exr_dir}.")
        sys.exit(1)

    # =============================================
    # Pass 1: determine the global min and max
    #         across the entire sequence
    # =============================================
    global_min = float('inf')
    global_max = float('-inf')

    print("Scanning all EXRs to find the global min/max...")
    for exr_path in exr_list:
        frame_min, frame_max = get_exr_min_max(exr_path, channel_name)
        if frame_min < global_min:
            global_min = frame_min
        if frame_max > global_max:
            global_max = frame_max

    if global_min == float('inf') or global_max == float('-inf'):
        print("Error: Could not determine the global min/max (invalid data?).")
        sys.exit(1)

    print(f"Global MIN: {global_min}")
    print(f"Global MAX: {global_max}")

    # =============================================
    # Pass 2: normalize and encode with FFmpeg
    # =============================================
    # Convert the first frame to determine the resolution
    first_rgba, w, h = exr_to_rgba8_bytes_with_global_scale(
        exr_list[0],
        channel_name,
        global_min,
        global_max
    )

    ffmpeg_cmd = [
        'ffmpeg',
        '-y',
        '-f', 'rawvideo',
        '-pix_fmt', 'rgba',
        '-s', f'{w}x{h}',
        '-r', '30',  # frame rate can be adjusted as needed
        '-i', 'pipe:0',
        '-c:v', 'ffv1',
        '-level', '3',
        output_file
    ]

    print("Running FFmpeg:")
    print(" ".join(ffmpeg_cmd))

    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    # Write the first frame
    proc.stdin.write(first_rgba)

    # Process and write the remaining frames
    for exr_path in exr_list[1:]:
        rgba_bytes, w2, h2 = exr_to_rgba8_bytes_with_global_scale(
            exr_path,
            channel_name,
            global_min,
            global_max
        )
        # Ensure the resolution remains consistent
        if w2 != w or h2 != h:
            print(
                f"Resolution mismatch in {exr_path} (expected {w}x{h}, got {w2}x{h2})")
            proc.stdin.close()
            proc.terminate()
            sys.exit(1)

        proc.stdin.write(rgba_bytes)

    proc.stdin.close()
    proc.wait()

    print(f"Done. The encoded video is saved as '{output_file}'.")


if __name__ == '__main__':
    main()
