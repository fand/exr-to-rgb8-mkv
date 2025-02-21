# exr-to-rgb8-mkv

This script converts depth maps in a `.exr` sequence into a mkv file.

Depth data in `.exr` files are stored in 32-bit float, so I packed them to RGBA8 like this:

```python
for y in range(height):
    for x in range(width):
        fval = depth_arr[y, x]
        b = struct.pack('<f', fval)  # float → 4bytes (little endian)
        rgba[y, x, 0] = b[0]  # R
        rgba[y, x, 1] = b[1]  # G
        rgba[y, x, 2] = b[2]  # B
        rgba[y, x, 3] = b[3]  # A
```

To use the `.mkv` video as a depth map, we have to unpack it in GLSL etc to obtain the depth data:

```glsl

```

## Usage

```
cd exr-to-rgb8-mkv
uv run main.py <EXR_DIRECTORY>
```

Then it'll output `output.mkv`.


## LICENSE

MIT
