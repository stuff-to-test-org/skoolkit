import zlib
import unittest
from collections import deque
from io import BytesIO

from skoolkittest import SkoolKitTestCase
from skoolkit.image import (ImageWriter, DEFAULT_FORMAT,
                            PNG_COMPRESSION_LEVEL, PNG_ENABLE_ANIMATION,
                            PNG_ALPHA, GIF_ENABLE_ANIMATION, GIF_TRANSPARENCY)
from skoolkit.graphics import Udg, Frame

TRANSPARENT = [0, 254, 0]
BLACK = [0, 0, 0]
BLUE = [0, 0, 197]
RED = [197, 0, 0]
MAGENTA = [197, 0, 197]
GREEN = [0, 198, 0]
CYAN = [0, 198, 197]
YELLOW = [197, 198, 0]
WHITE = [205, 198, 205]
BRIGHT_BLUE = [0, 0, 255]
BRIGHT_RED = [255, 0, 0]
BRIGHT_MAGENTA = [255, 0, 255]
BRIGHT_GREEN = [0, 255, 0]
BRIGHT_CYAN = [0, 255, 255]
BRIGHT_YELLOW = [255, 255, 0]
BRIGHT_WHITE = [255, 255, 255]

PALETTE = [
    TRANSPARENT,
    BLACK,
    BLUE,
    RED,
    MAGENTA,
    GREEN,
    CYAN,
    YELLOW,
    WHITE,
    BRIGHT_BLUE,
    BRIGHT_RED,
    BRIGHT_MAGENTA,
    BRIGHT_GREEN,
    BRIGHT_CYAN,
    BRIGHT_YELLOW,
    BRIGHT_WHITE
]

PNG_SIGNATURE = [137, 80, 78, 71, 13, 10, 26, 10]
IHDR = [73, 72, 68, 82]
PLTE = [80, 76, 84, 69]
TRNS = [116, 82, 78, 83]
ACTL = [97, 99, 84, 76]
FCTL = [102, 99, 84, 76]
FDAT = [102, 100, 65, 84]
IDAT = [73, 68, 65, 84]
IEND_CHUNK = [0, 0, 0, 0, 73, 69, 78, 68, 174, 66, 96, 130]

CRC_MASK = 4294967295

GIF_HEADER = [71, 73, 70, 56, 57, 97]
AEB = [33, 255, 11, 78, 69, 84, 83, 67, 65, 80, 69, 50, 46, 48, 3, 1, 0, 0, 0]
GIF_FRAME_DELAY = 32
GIF_TRAILER = 59

def create_crc_table():
    crc_table = []
    for n in range(256):
        c = n
        for k in range(8):
            if c & 1:
                c = 3988292384 ^ (c >> 1)
            else:
                c = c >> 1
        crc_table.append(c)
    return crc_table

def create_attr_index():
    attr_index = {}
    for attr in range(128):
        if attr & 64:
            ink = 8 + (attr & 7)
            paper = 8 + (attr & 56) // 8
            if ink == 8:
                ink = 1
            if paper == 8:
                paper = 1
        else:
            ink = 1 + (attr & 7)
            paper = 1 + (attr & 56) // 8
        attr_index[attr] = (paper, ink)
    return attr_index

CRC_TABLE = create_crc_table()
ATTR_INDEX = create_attr_index()

class ImageWriterOptionsTest(SkoolKitTestCase):
    def test_change_option_values(self):
        options = {
            DEFAULT_FORMAT: 'gif',
            PNG_COMPRESSION_LEVEL: 3,
            GIF_TRANSPARENCY: 1
        }
        image_writer = ImageWriter(options=options)
        self.assertEqual(image_writer.options[DEFAULT_FORMAT], 'gif')
        self.assertEqual(image_writer.options[PNG_COMPRESSION_LEVEL], 3)
        self.assertEqual(image_writer.options[GIF_TRANSPARENCY], 1)

    def test_default_option_values(self):
        image_writer = ImageWriter()
        self.assertEqual(image_writer.options[DEFAULT_FORMAT], 'png')
        self.assertEqual(image_writer.options[PNG_COMPRESSION_LEVEL], 9)
        self.assertEqual(image_writer.options[PNG_ENABLE_ANIMATION], 1)
        self.assertEqual(image_writer.options[PNG_ALPHA], 255)
        self.assertEqual(image_writer.options[GIF_ENABLE_ANIMATION], 1)
        self.assertEqual(image_writer.options[GIF_TRANSPARENCY], 0)

    def test_invalid_option_value(self):
        image_writer = ImageWriter(options={PNG_COMPRESSION_LEVEL: 'NaN'})
        self.assertEqual(image_writer.options[PNG_COMPRESSION_LEVEL], 9)

class ImageWriterTest:
    def _get_num(self, stream, index):
        return index + 1, stream[index]

    def _get_dword(self, stream, index):
        return index + 4, 16777216 * stream[index] + 65536 * stream[index + 1] + 256 * stream[index + 2] + stream[index + 3]

    def _get_image_data(self, image_writer, udg_array, img_format, scale=1, mask=0, x=0, y=0, width=None, height=None):
        frame = Frame(udg_array, scale, mask, x, y, width, height)
        img_stream = BytesIO()
        image_writer.write_image([frame], img_stream, img_format)
        img_bytes = [b for b in img_stream.getvalue()]
        img_stream.close()
        return img_bytes

    def _get_animated_image_data(self, image_writer, frames, img_format):
        img_stream = BytesIO()
        image_writer.write_image(frames, img_stream, img_format)
        img_bytes = [b for b in img_stream.getvalue()]
        img_stream.close()
        return img_bytes

    def _get_pixels_from_udg_array(self, udg_array, scale, mask, x0=0, y0=0, width=None, height=None):
        full_width = 8 * len(udg_array[0]) * scale
        full_height = 8 * len(udg_array) * scale
        width = min(width or full_width, full_width - x0)
        height = min(height or full_height, full_height - y0)
        cropped = width < full_width or height < full_height
        x1 = x0 + width
        y1 = y0 + height
        inc = 8 * scale
        min_col = x0 // inc
        max_col = x1 // inc
        min_row = y0 // inc
        max_row = y1 // inc
        x0_floor = inc * min_col
        y0_floor = inc * min_row

        palette = []
        pixels = []
        pixels2 = []
        mask = int(mask)
        has_masks = 0
        all_masked = 1
        min_x = width
        min_y = height
        max_x = max_y = 0
        frames_differ = False

        y = y0_floor
        for row in udg_array[min_row:max_row + 1]:
            min_j = max(0, (y0 - y) // scale)
            max_j = min(8, 1 + (y1 - y - 1) // scale)
            y += min_j * scale
            row_flashing = False
            min_y_floor = len(pixels)
            for j in range(min_j, max_j):
                if y < y0:
                    rows = min(y - y0 + scale, height)
                else:
                    rows = min(y1 - y, scale)
                pixel_row = []
                pixel_row2 = []
                x = x0_floor
                for udg in row[min_col:max_col + 1]:
                    attr = udg.attr
                    paper, ink = ATTR_INDEX[attr & 127]
                    p_rgb = PALETTE[paper]
                    i_rgb = PALETTE[ink]
                    byte = udg.data[j]
                    if udg.mask:
                        has_masks = 1
                    else:
                        all_masked = 0
                    if mask and udg.mask:
                        mask_byte = udg.mask[j]
                    else:
                        mask_byte = 0
                    min_k = max(0, (x0 - x) // scale)
                    max_k = min(8, 1 + (x1 - x - 1) // scale)
                    x += min_k * scale
                    udg_flashing = attr & 128 and paper != ink
                    has_non_trans = False
                    byte <<= min_k
                    mask_byte <<= min_k
                    min_x_floor = len(pixel_row)
                    for k in range(min_k, max_k):
                        if x < x0:
                            cols = min(x - x0 + scale, width)
                        else:
                            cols = min(x1 - x, scale)
                        ink_p = (i_rgb,) * cols
                        paper_p = (p_rgb,) * cols
                        trans_p = (TRANSPARENT,) * cols
                        if mask == 1 and udg.mask:
                            if mask_byte & 128 == 0:
                                pixel, f_pixel = paper_p, ink_p
                            elif byte & 128:
                                pixel, f_pixel = ink_p, paper_p
                            else:
                                pixel = f_pixel = trans_p
                        elif mask == 2 and udg.mask:
                            if byte & 128:
                                pixel, f_pixel = ink_p, paper_p
                            elif mask_byte & 128:
                                pixel = f_pixel = trans_p
                            else:
                                pixel, f_pixel = paper_p, ink_p
                        else:
                            if byte & 128:
                                pixel, f_pixel = ink_p, paper_p
                            else:
                                pixel, f_pixel = paper_p, ink_p
                        pixel_rgb = pixel[0]
                        if pixel_rgb != TRANSPARENT:
                            has_non_trans = True
                        if pixel_rgb not in palette:
                            palette.append(pixel_rgb)
                        pixel_row.extend(pixel)
                        if udg_flashing:
                            f_pixel_rgb = f_pixel[0]
                            if f_pixel_rgb not in palette:
                                palette.append(f_pixel_rgb)
                            pixel_row2.extend(f_pixel)
                            frames_differ = frames_differ or f_pixel != pixel
                        else:
                            pixel_row2.extend(pixel)
                        byte *= 2
                        mask_byte *= 2
                        x += scale
                    if udg_flashing and has_non_trans:
                        min_x = min(min_x_floor, min_x)
                        max_x = max(len(pixel_row), max_x)
                        row_flashing = True
                pixels += [pixel_row] * rows
                pixels2 += [pixel_row2] * rows
                if row_flashing:
                    min_y = min(min_y_floor, min_y)
                    max_y = max(len(pixels), max_y)
                y += scale

        if frames_differ:
            frame2_xy = (min_x, min_y)
            pixels2 = [pixels2[i][min_x:max_x] for i in range(min_y, max_y)]
        else:
            pixels2 = frame2_xy = None

        masks = has_masks + all_masked
        return palette, masks, pixels, pixels2, frame2_xy

    def _test_scales(self, udg_array, scales=(1, 2, 3, 4), mask=0, x=0, y=0, width=None, height=None, iw_args=None, exp_pixels=None):
        for scale in scales:
            s_w = len(udg_array[0]) * 8 * (scale - 1) + width if width is not None else None
            s_h = len(udg_array) * 8 * (scale - 1) + height if height is not None else None
            self._test_image(udg_array, scale, mask, x, y, s_w, s_h, iw_args, exp_pixels)

    ###########################################################################

    def test_bd0(self):
        # No mask, single colour
        udg = Udg(56, (255,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array)

    def test_bd0_flashing(self):
        # No mask, single colour, FLASH bit set
        udg = Udg(137, (0,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array)

    def test_bd0_cropped(self):
        # No mask, single colour, cropped
        udg = Udg(56, (255,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, x=1, y=2, width=6, height=5)

    def test_bd0_cropped_flashing(self):
        # No mask, single colour, cropped, FLASH bit set
        udg = Udg(137, (0,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, x=2, y=1, width=5, height=6)

    def test_bd0_mask1(self):
        # OR-AND mask, single colour (transparent)
        udg = Udg(56, (0,) * 8, (255,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=1)

    def test_bd0_mask1_flashing(self):
        # OR-AND mask, single colour (transparent), FLASH bit set
        udg = Udg(184, (0,) * 8, (255,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=1)

    def test_bd0_mask1_cropped(self):
        # OR-AND mask, single colour (transparent), cropped
        udg = Udg(56, (0,) * 8, (255,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=1, x=3, y=1, width=4, height=6)

    def test_bd0_mask1_cropped_flashing(self):
        # OR-AND mask, single colour (transparent), cropped, FLASH bit set
        udg = Udg(184, (0,) * 8, (255,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=1, x=3, y=1, width=4, height=6)

    def test_bd0_mask2(self):
        # AND-OR mask, single colour (transparent)
        udg = Udg(56, (0,) * 8, (255,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=2)

    def test_bd0_mask2_flashing(self):
        # AND-OR mask, single colour (transparent), FLASH bit set
        udg = Udg(184, (0,) * 8, (255,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=2)

    def test_bd0_mask2_cropped(self):
        # AND-OR mask, single colour (transparent), cropped
        udg = Udg(56, (0,) * 8, (255,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=2, x=3, y=1, width=4, height=6)

    def test_bd0_mask2_cropped_flashing(self):
        # AND-OR mask, single colour (transparent), cropped, FLASH bit set
        udg = Udg(184, (0,) * 8, (255,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=2, x=3, y=1, width=4, height=6)

    ###########################################################################

    def test_bd1(self):
        # No mask, 2 colours
        udg = Udg(49, (164,) * 8)
        udg_array = [[udg] * 2]
        self._test_scales(udg_array)

    def test_bd1_flashing(self):
        # No mask, 2 colours, flashing
        udg = Udg(177, (164,) * 8)
        udg_array = [[udg] * 2]
        self._test_scales(udg_array)

    def test_bd1_cropped(self):
        # No mask, 2 colours, cropped
        udg = Udg(5, (148,) * 8)
        udg_array = [[udg] * 2] * 2
        self._test_scales(udg_array, x=1, y=2, width=9, height=11)

    def test_bd1_cropped_width_less_than_scale(self):
        # No mask, 2 colours, cropped, width less than scale
        udg = Udg(5, (148,) * 8)
        udg_array = [[udg] * 2] * 2
        self._test_image(udg_array, scale=3, x=4, width=1)
        self._test_image(udg_array, scale=10, x=1, width=1)

    def test_bd1_cropped_height_less_than_scale(self):
        # No mask, 2 colours, cropped, height less than scale
        udg = Udg(5, (148,) * 8)
        udg_array = [[udg] * 2] * 2
        self._test_image(udg_array, scale=3, y=4, height=1)
        self._test_image(udg_array, scale=10, y=1, height=1)

    def test_bd1_cropped_flashing(self):
        # No mask, 2 colours, cropped, flashing
        udg = Udg(129, (0,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, x=2, y=1, width=5, height=6)

    def test_bd1_mask1_ink(self):
        # OR-AND mask, two colours (trans + ink)
        udg = Udg(49, (136,) * 8, (255,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=1)

    def test_bd1_mask1_paper(self):
        # OR-AND mask, two colours (trans + paper)
        udg = Udg(8, (0,) * 8, (88,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=1)

    def test_bd1_mask1_flashing_no_trans(self):
        # OR-AND mask, flashing, no transparent bits
        udg = Udg(184, (1,) * 8, (1,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=1)

    def test_bd1_mask1_cropped(self):
        # OR-AND mask, two colours (trans + ink), cropped
        udg = Udg(49, (136,) * 8, (255,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=1, x=1, y=2, width=5, height=5)

    def test_bd1_mask1_cropped_flashing(self):
        # OR-AND mask, INK = PAPER, cropped, FLASH bit set
        udg = Udg(137, (136,) * 8, (255,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=1, x=2, y=1, width=5, height=5)

    def test_bd1_mask2_ink(self):
        # AND-OR mask, two colours (trans + ink)
        udg = Udg(49, (136,) * 8, (255,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=2)

    def test_bd1_mask2_paper(self):
        # AND-OR mask, two colours (trans + paper)
        udg = Udg(8, (0,) * 8, (88,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=2)

    def test_bd1_mask2_flashing_no_trans(self):
        # AND-OR mask, flashing, no transparent bits
        udg = Udg(184, (1,) * 8, (1,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=2)

    def test_bd1_mask2_cropped(self):
        # AND-OR mask, two colours (trans + ink), cropped
        udg = Udg(49, (136,) * 8, (255,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=2, x=1, y=2, width=5, height=5)

    def test_bd1_mask2_cropped_flashing(self):
        # AND-OR mask, INK = PAPER, cropped, FLASH bit set
        udg = Udg(137, (136,) * 8, (255,) * 8)
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=2, x=2, y=1, width=5, height=5)

    def test_bd1_attribute_with_same_ink_and_paper(self):
        # No mask, 2 colours, 2 UDGs, 2 attributes - one with INK and PAPER the
        # same colour
        udg1 = Udg(7, (1,) * 8)  # INK 7: PAPER 0
        udg2 = Udg(63, (2,) * 8) # INK 7: PAPER 7
        udg_array = [[udg1], [udg2]]
        self._test_image(udg_array)

    def test_bd1_mask2_one_udg_maskless(self):
        # AND-OR mask, one UDG with no mask
        udg1 = Udg(7, (15,) * 8, (31,) * 8)
        udg2 = Udg(7, (240,) * 8)
        udg_array = [[udg1, udg2]]
        self._test_image(udg_array, mask=2)

    ###########################################################################

    def test_bd2(self):
        # No mask, 4 colours
        udg1 = Udg(56, (93,) * 8)  # INK 0: PAPER 7
        udg2 = Udg(49, (162,) * 8) # INK 1: PAPER 6
        udg_array = [[udg1, udg2]]
        self._test_scales(udg_array)

    def test_bd2_flashing(self):
        # No mask, 4 colours, flashing
        udg1 = Udg(56, (93,) * 8)   # INK 0: PAPER 7: FLASH 1
        udg2 = Udg(177, (162,) * 8) # INK 1: PAPER 6: FLASH 1
        udg_array = [[udg1, udg2]]
        self._test_scales(udg_array)

    def test_bd2_cropped(self):
        # No mask, 3 colours, cropped
        udg1 = Udg(30, (170,) * 8) # INK 6: PAPER 3
        udg2 = Udg(28, (81,) * 8)  # INK 4: PAPER 3
        udg_array = [[udg1, udg2]] * 2
        self._test_scales(udg_array, x=3, y=4, width=11, height=11)

    def test_bd2_cropped_width_less_than_scale(self):
        # No mask, 3 colours, cropped, width less than scale
        udg1 = Udg(30, (170,) * 8) # INK 6: PAPER 3
        udg2 = Udg(28, (81,) * 8)  # INK 4: PAPER 3
        udg_array = [[udg1, udg2]] * 2
        self._test_image(udg_array, scale=3, x=4, width=1)
        self._test_image(udg_array, scale=10, x=1, width=1)

    def test_bd2_cropped_height_less_than_scale(self):
        # No mask, 3 colours, cropped, height less than scale
        udg1 = Udg(30, (170,) * 8) # INK 6: PAPER 3
        udg2 = Udg(28, (81,) * 8)  # INK 4: PAPER 3
        udg_array = [[udg1, udg2]] * 2
        self._test_image(udg_array, scale=3, y=4, height=1)
        self._test_image(udg_array, scale=10, y=1, height=1)

    def test_bd2_cropped_flashing(self):
        # No mask, 3 colours, cropped, flashing
        udg1 = Udg(129, (0,) * 8)   # INK 1: PAPER 0: FLASH 1
        udg2 = Udg(130, (255,) * 8) # INK 2: PAPER 0: FLASH 1
        udg_array = [[udg1, udg2]]
        self._test_scales(udg_array, x=1, y=3, width=13, height=4)

    def test_bd2_mask1(self):
        # OR-AND mask, 2 colours + trans
        udg = Udg(88, (34,) * 8, (119,) * 8) # INK 0: PAPER 3: BRIGHT 1
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=1)

    def test_bd2_mask1_flashing(self):
        # OR-AND mask, 2 colours + trans, one UDG flashing
        udg1 = Udg(56, (1,) * 8) # INK 0: PAPER 7: FLASH 0
        udg2 = Udg(184, (0,) * 8, (255, 129, 129, 129, 129, 129, 129, 255)) # INK 0: PAPER 7: FLASH 1
        udg_array = [[udg1, udg2]]
        self._test_scales(udg_array, mask=1)

    def test_bd2_mask1_cropped(self):
        # OR-AND mask, 3 colours + trans, cropped
        udg1 = Udg(88, (34,) * 8, (119,) * 8) # INK 0: PAPER 3: BRIGHT 1
        udg2 = Udg(89, (34,) * 8, (119,) * 8) # INK 1: PAPER 3: BRIGHT 1
        udg_array = [[udg1, udg2], [udg2, udg1]]
        self._test_scales(udg_array, mask=1, x=2, y=2, width=13, height=11)

    def test_bd2_mask1_cropped_flashing(self):
        # OR-AND mask, 2 colours + trans, cropped, one UDG flashing
        udg1 = Udg(56, (1,) * 8) # INK 0: PAPER 7: FLASH 0
        udg2 = Udg(184, (0,) * 8, (255, 255, 195, 195, 195, 195, 255, 255)) # INK 0: PAPER 7: FLASH 1
        udg_array = [[udg1, udg2]]
        self._test_scales(udg_array, mask=1, x=1, y=1, width=14, height=6)

    def test_bd2_mask2(self):
        # AND-OR mask, 2 colours + trans
        udg = Udg(56, (170,) * 8, (170,) + (255,) * 7) # INK 0: PAPER 7
        udg_array = [[udg]]
        self._test_scales(udg_array, mask=2)

    def test_bd2_mask2_flashing(self):
        # AND-OR mask, 2 colours + trans, one UDG flashing
        udg1 = Udg(56, (1,) * 8) # INK 0: PAPER 7: FLASH 0
        udg2 = Udg(184, (0,) * 8, (255, 129, 129, 129, 129, 129, 129, 255)) # INK 0: PAPER 7: FLASH 1
        udg_array = [[udg1, udg2]]
        self._test_scales(udg_array, mask=2)

    def test_bd2_mask2_cropped(self):
        # AND-OR mask, 3 colours + trans, cropped
        udg1 = Udg(88, (34,) * 8, (119,) * 8) # INK 0: PAPER 3: BRIGHT 1
        udg2 = Udg(89, (34,) * 8, (119,) * 8) # INK 1: PAPER 3: BRIGHT 1
        udg_array = [[udg1, udg2], [udg2, udg1]]
        self._test_scales(udg_array, mask=2, x=1, y=3, width=13, height=11)

    def test_bd2_mask2_cropped_flashing(self):
        # AND-OR mask, 2 colours + trans, cropped, one UDG flashing
        udg1 = Udg(56, (1,) * 8) # INK 0: PAPER 7: FLASH 0
        udg2 = Udg(184, (0,) * 8, (255, 255, 195, 195, 195, 195, 255, 255)) # INK 0: PAPER 7: FLASH 1
        udg_array = [[udg1, udg2]]
        self._test_scales(udg_array, mask=2, x=1, y=1, width=14, height=6)

    ###########################################################################

    def test_bd4(self):
        # No mask, 6 colours
        udg1 = Udg(49, (136,) * 8) # INK 1: PAPER 6
        udg2 = Udg(42, (68,) * 8)  # INK 2: PAPER 5
        udg3 = Udg(35, (34,) * 8)  # INK 3: PAPER 4
        udg_array = [[udg1, udg2, udg3]]
        self._test_scales(udg_array)

    def test_bd4_flashing(self):
        # No mask, 6 colours, flashing
        udg1 = Udg(49, (136,) * 8) # INK 1: PAPER 6
        udg2 = Udg(170, (68,) * 8) # INK 2: PAPER 5
        udg3 = Udg(35, (34,) * 8)  # INK 3: PAPER 4
        udg_array = [[udg1, udg2, udg3]]
        self._test_scales(udg_array)

    def test_bd4_cropped(self):
        # No mask, 5 colours, cropped
        udg1 = Udg(30, (170,) * 8) # INK 6: PAPER 3
        udg2 = Udg(28, (81,) * 8)  # INK 4: PAPER 3
        udg3 = Udg(5, (129,) * 8)  # INK 5: PAPER 0
        udg_array = [[udg1, udg2], [udg3, udg1]]
        self._test_scales(udg_array, x=2, y=1, width=11, height=9)

    def test_bd4_cropped_width_less_than_scale(self):
        # No mask, 5 colours, cropped, width less than scale
        udg1 = Udg(30, (170,) * 8) # INK 6: PAPER 3
        udg2 = Udg(28, (81,) * 8)  # INK 4: PAPER 3
        udg3 = Udg(5, (129,) * 8)  # INK 5: PAPER 0
        udg_array = [[udg1], [udg2], [udg3]]
        self._test_image(udg_array, scale=3, x=4, width=1)
        self._test_image(udg_array, scale=10, x=1, width=1)

    def test_bd4_cropped_height_less_than_scale(self):
        # No mask, 5 colours, cropped, height less than scale
        udg1 = Udg(30, (170,) * 8) # INK 6: PAPER 3
        udg2 = Udg(28, (81,) * 8)  # INK 4: PAPER 3
        udg3 = Udg(5, (129,) * 8)  # INK 5: PAPER 0
        udg_array = [[udg1, udg2, udg3]]
        self._test_image(udg_array, scale=3, y=4, height=1)
        self._test_image(udg_array, scale=10, y=1, height=1)

    def test_bd4_cropped_flashing(self):
        # No mask, 6 colours, cropped, flashing
        udg1 = Udg(129, (0,) * 8)   # INK 1: PAPER 0: FLASH 1
        udg2 = Udg(147, (255,) * 8) # INK 3: PAPER 2: FLASH 1
        udg3 = Udg(165, (0,) * 8)   # INK 5: PAPER 4: FLASH 1
        udg_array = [[udg1, udg2, udg3]] * 3
        self._test_scales(udg_array, x=1, y=2, width=20, height=21)

    def test_bd4_mask1(self):
        # OR-AND mask, 5 colours + trans
        udg1 = Udg(46, (15,) * 8)             # INK 6: PAPER 5
        udg2 = Udg(120, (0,) * 8, (240,) * 8) # PAPER 7: BRIGHT 1
        udg3 = Udg(74, (15,) * 8)             # INK 2: PAPER 1: BRIGHT 1
        udg_array = [[udg1, udg2, udg3]]
        self._test_scales(udg_array, mask=1)

    def test_bd4_mask1_flashing(self):
        # OR-AND mask, 6 colours + trans, flashing
        udg1 = Udg(184, (240,) * 8, (243,) * 8) # INK 0: PAPER 7: FLASH 1
        udg2 = Udg(49, (170,) * 8)              # INK 1: PAPER 6
        udg3 = Udg(170, (195,) * 8)             # INK 2: PAPER 5: FLASH 1
        udg_array = [[udg1, udg2, udg3]]
        self._test_scales(udg_array, mask=1)

    def test_bd4_mask1_cropped(self):
        # OR-AND mask, 4 colours + trans, cropped
        udg1 = Udg(24, (34,) * 8, (119,) * 8) # INK 0: PAPER 3
        udg2 = Udg(57, (170,) * 8)            # INK 1: PAPER 7
        udg_array = [[udg1, udg2], [udg2, udg1]]
        self._test_scales(udg_array, mask=1, x=1, y=3, width=13, height=11)

    def test_bd4_mask1_cropped_flashing(self):
        # OR-AND mask, 4 colours + trans, cropped, flashing
        udg1 = Udg(152, (34,) * 8, (119,) * 8) # INK 0: PAPER 3: FLASH 1
        udg2 = Udg(57, (170,) * 8)             # INK 1: PAPER 7
        udg_array = [[udg1, udg2], [udg2, udg1]]
        self._test_scales(udg_array, mask=1, x=1, y=3, width=13, height=11)

    def test_bd4_mask2(self):
        # AND-OR mask, 5 colours + trans
        udg1 = Udg(46, (15,) * 8)             # INK 6: PAPER 5
        udg2 = Udg(120, (0,) * 8, (240,) * 8) # PAPER 7: BRIGHT 1
        udg3 = Udg(74, (15,) * 8)             # INK 2: PAPER 1: BRIGHT 1
        udg_array = [[udg1, udg2, udg3]]
        self._test_scales(udg_array, mask=2)

    def test_bd4_mask2_flashing(self):
        # AND-OR mask, 6 colours + trans, flashing
        udg1 = Udg(184, (240,) * 8, (243,) * 8) # INK 0: PAPER 7: FLASH 1
        udg2 = Udg(49, (170,) * 8)              # INK 1: PAPER 6
        udg3 = Udg(170, (195,) * 8)             # INK 2: PAPER 5: FLASH 1
        udg_array = [[udg1, udg2, udg3]]
        self._test_scales(udg_array, mask=2)

    def test_bd4_mask2_cropped(self):
        # AND-OR mask, 4 colours + trans, cropped
        udg1 = Udg(24, (34,) * 8, (119,) * 8) # INK 0: PAPER 3
        udg2 = Udg(57, (170,) * 8)            # INK 1: PAPER 7
        udg_array = [[udg1, udg2], [udg2, udg1]]
        self._test_scales(udg_array, mask=2, x=1, y=3, width=13, height=11)

    def test_bd4_mask2_cropped_flashing(self):
        # AND-OR mask, 4 colours + trans, cropped, flashing
        udg1 = Udg(152, (34,) * 8, (119,) * 8) # INK 0: PAPER 3: FLASH 1
        udg2 = Udg(57, (170,) * 8)             # INK 1: PAPER 7
        udg_array = [[udg1, udg2], [udg2, udg1]]
        self._test_scales(udg_array, mask=2, x=1, y=3, width=13, height=11)

    ###########################################################################

    def test_all_colours(self):
        # All 15 colours
        udg1 = Udg(56, (15,) * 8)  # white, black
        udg2 = Udg(10, (15,) * 8)  # blue, red
        udg3 = Udg(28, (15,) * 8)  # magenta, green
        udg4 = Udg(46, (15,) * 8)  # cyan, yellow
        udg5 = Udg(120, (0,) * 8)  # bright white
        udg6 = Udg(74, (15,) * 8)  # bright blue, bright red
        udg7 = Udg(92, (15,) * 8)  # bright magenta, bright green
        udg8 = Udg(110, (15,) * 8) # bright cyan, bright yellow
        udg_array = [[udg1, udg2, udg3, udg4], [udg5, udg6, udg7, udg8]]
        self._test_image(udg_array)

    def test_all_colours_plus_transparent(self):
        # All 15 colours + trans
        udg1 = Udg(56, (15,) * 8)             # white, black
        udg2 = Udg(10, (15,) * 8)             # blue, red
        udg3 = Udg(28, (15,) * 8)             # magenta, green
        udg4 = Udg(46, (15,) * 8)             # cyan, yellow
        udg5 = Udg(120, (0,) * 8, (240,) * 8) # trans, bright white
        udg6 = Udg(74, (15,) * 8)             # bright blue, bright red
        udg7 = Udg(92, (15,) * 8)             # bright magenta, bright green
        udg8 = Udg(110, (15,) * 8)            # bright cyan, bright yellow
        udg_array = [[udg1, udg2, udg3, udg4], [udg5, udg6, udg7, udg8]]
        self._test_image(udg_array, mask=1)

    def test_cropped_colours(self):
        # All 15 colours, colours cropped off
        udg1 = Udg(56, (15,) * 8)  # white, black
        udg2 = Udg(10, (15,) * 8)  # blue, red
        udg3 = Udg(28, (15,) * 8)  # magenta, green
        udg4 = Udg(46, (15,) * 8)  # cyan, yellow
        udg5 = Udg(120, (0,) * 8)  # bright white
        udg6 = Udg(74, (15,) * 8)  # bright blue, bright red
        udg7 = Udg(92, (15,) * 8)  # bright magenta, bright green
        udg8 = Udg(110, (15,) * 8) # bright cyan, bright yellow
        udg_array = [[udg1, udg2, udg3, udg4], [udg5, udg6, udg7, udg8]]
        self._test_image(udg_array, scale=2, x=1)
        self._test_image(udg_array, scale=3, x=12)
        self._test_image(udg_array, scale=2, x=20)
        self._test_image(udg_array, scale=2, width=56)
        self._test_image(udg_array, scale=2, width=44)
        self._test_image(udg_array, scale=2, y=1)
        self._test_image(udg_array, scale=2, y=24)
        self._test_image(udg_array, scale=2, height=18)
        self._test_image(udg_array, scale=2, height=14)

    def test_mask1_alpha(self):
        # OR-AND mask, alpha < 255
        iw_args = {'options': self.alpha_option}
        udg = Udg(88, (34,) * 8, (163,) * 8)
        udg_array = [[udg]]
        self._test_image(udg_array, mask=1, iw_args=iw_args)

    def test_mask1_no_transparency(self):
        # OR-AND mask, no transparent bits
        udg = Udg(56, (255,) * 8, (1,) * 8)
        udg_array = [[udg]]
        self._test_image(udg_array, mask=1)

    def test_mask1_cropped_no_transparency(self):
        # OR-AND mask, cropped, no transparent bits
        udg = Udg(56, (255,) * 8, (1,) * 8)
        udg_array = [[udg]]
        self._test_image(udg_array, mask=1, y=2)

    def test_mask1_flashing_one_udg_all_transparent(self):
        # OR-AND mask, flashing, one UDG all transparent
        udg1 = Udg(135, (0,) * 8, (255,) * 8)
        udg2 = Udg(135, (240,) * 8)
        udg_array = [[udg1, udg2]]
        self._test_image(udg_array, scale=2, mask=1)

    def test_mask1_cropped_flashing_one_udg_all_transparent(self):
        # OR-AND mask, cropped, flashing, one UDG all transparent
        udg1 = Udg(135, (0,) * 8, (255,) * 8)
        udg2 = Udg(184, (240,) * 8)
        udg_array = [[udg1, udg2]]
        self._test_image(udg_array, scale=2, mask=1, x=1, y=1, width=27, height=13)

    def test_mask1_flashing_no_animation(self):
        # OR-AND mask, flashing, no animation
        iw_args = {'options': {self.animation_flag: 0}}
        udg = Udg(184, (240,) * 8, (243,) * 8)
        udg_array = [[udg]]
        self._test_image(udg_array, mask=1, iw_args=iw_args)

    def test_alpha_no_mask(self):
        # No mask, alpha < 255
        iw_args = {'options': self.alpha_option}
        udg = Udg(56, (132,) * 8)
        udg_array = [[udg]]
        self._test_image(udg_array, iw_args=iw_args)

    def test_flashing_no_animation(self):
        # No mask, flashing, no animation
        iw_args = {'options': {self.animation_flag: 0}}
        udg = Udg(184, (240,) * 8)
        udg_array = [[udg]]
        self._test_image(udg_array, iw_args=iw_args)

    def test_custom_colours(self):
        # Two custom colours
        indigo = [75, 0, 130]
        salmon = [250, 128, 114]
        colours = {'BLUE': indigo, 'RED': salmon}
        iw_args = {'palette': colours}
        udg = Udg(10, (195,) * 8) # 11000011
        udg_array = [[udg]]
        exp_pixels = [[salmon, salmon, indigo, indigo, indigo, indigo, salmon, salmon]] * 8
        self._test_image(udg_array, iw_args=iw_args, exp_pixels=exp_pixels)

    def test_animation(self):
        # 3 frames, 2 colours, 16x8
        frame1 = Frame([[Udg(6, (128,) * 8), Udg(6, (0,) * 8)]], delay=20)
        frame2 = Frame([[Udg(6, (64,) * 8), Udg(6, (1,) * 8)]], delay=100)
        frame3 = Frame([[Udg(6, (32,) * 8), Udg(6, (2,) * 8)]], delay=150)
        frames = [frame1, frame2, frame3]
        self._test_animated_image(frames)

    def test_animation_cropped(self):
        # 2 frames, 4 colours, 4x4
        frame1 = Frame([[Udg(56, (128,) * 8)]], x=1, y=1, width=4, height=4)
        frame2 = Frame([[Udg(49, (64,) * 8)]], x=2, y=3, width=4, height=4)
        frames = [frame1, frame2]
        self._test_animated_image(frames)

    def test_animation_mask1(self):
        # 2 frames, transparency on frame 2
        iw_args = {'options': self.alpha_option}
        frame1 = Frame([[Udg(49, (64,) * 8)]])
        frame2 = Frame([[Udg(184, (240,) * 8, (243,) * 8)]], mask=1)
        frames = [frame1, frame2]
        self._test_animated_image(frames, iw_args)

    def test_animation_with_frames_of_different_sizes(self):
        # First frame 16x8, second frame 8x16, third frame 8x8
        frame1 = Frame([[Udg(1, (0,) * 8)] * 2])
        frame2 = Frame([[Udg(1, (0,) * 8)]] * 2)
        frame3 = Frame([[Udg(1, (0,) * 8)]])
        frames = [frame1, frame2, frame3]
        self._test_animated_image(frames)

class PngWriterTest(SkoolKitTestCase, ImageWriterTest):
    def setUp(self):
        SkoolKitTestCase.setUp(self)
        self.animation_flag = PNG_ENABLE_ANIMATION
        self.alpha_option = {PNG_ALPHA: 127}

    def _get_word(self, stream, index):
        return index + 2, 256 * stream[index] + stream[index + 1]

    def _get_crc(self, byte_list):
        crc = CRC_MASK
        for b in byte_list:
            crc = CRC_TABLE[(crc ^ b) & 255] ^ (crc >> 8)
        return crc ^ CRC_MASK

    def _get_chunk_type(self, stream, index):
        return index + 4, stream[index:index + 4]

    def _check_signature(self, img_bytes):
        i = len(PNG_SIGNATURE)
        self.assertEqual(PNG_SIGNATURE, img_bytes[:i])
        return i

    def _check_ihdr(self, img_bytes, index, exp_width, exp_height, exp_bit_depth):
        i = index
        i, chunk_length = self._get_dword(img_bytes, i)
        self.assertEqual(chunk_length, 13)
        ihdr_start = i
        i, chunk_type = self._get_chunk_type(img_bytes, i)
        self.assertEqual(IHDR, chunk_type)
        i, image_width = self._get_dword(img_bytes, i)
        self.assertEqual(image_width, exp_width)
        i, image_height = self._get_dword(img_bytes, i)
        self.assertEqual(image_height, exp_height)
        i, bit_depth = self._get_num(img_bytes, i)
        self.assertEqual(bit_depth, exp_bit_depth)
        i, colour_type = self._get_num(img_bytes, i)
        self.assertEqual(colour_type, 3)
        i, compression_method = self._get_num(img_bytes, i)
        self.assertEqual(compression_method, 0)
        i, filter_method = self._get_num(img_bytes, i)
        self.assertEqual(filter_method, 0)
        i, interlace_method = self._get_num(img_bytes, i)
        self.assertEqual(interlace_method, 0)
        ihdr_end = i
        i, ihdr_crc = self._get_dword(img_bytes, i)
        self.assertEqual(ihdr_crc, self._get_crc(img_bytes[ihdr_start:ihdr_end]))
        return i

    def _check_plte(self, img_bytes, index, exp_palette):
        i = index
        i, chunk_length = self._get_dword(img_bytes, i)
        self.assertEqual(chunk_length, len(exp_palette) * 3)
        plte_start = i
        i, chunk_type = self._get_chunk_type(img_bytes, i)
        self.assertEqual(PLTE, chunk_type)
        palette = [img_bytes[j:j + 3] for j in range(i, i + chunk_length, 3)]
        i += chunk_length
        self.assertEqual(sorted(exp_palette), sorted(palette))
        plte_end = i
        i, plte_crc = self._get_dword(img_bytes, i)
        self.assertEqual(plte_crc, self._get_crc(img_bytes[plte_start:plte_end]))
        return i, palette

    def _check_trns(self, img_bytes, index, exp_alpha):
        i = index
        i, chunk_length = self._get_dword(img_bytes, i)
        self.assertEqual(chunk_length, 1)
        trns_start = i
        i, chunk_type = self._get_chunk_type(img_bytes, i)
        self.assertEqual(chunk_type, TRNS)
        alpha = img_bytes[i]
        self.assertEqual(alpha, exp_alpha)
        i += chunk_length
        trns_end = i
        i, trns_crc = self._get_dword(img_bytes, i)
        self.assertEqual(trns_crc, self._get_crc(img_bytes[trns_start:trns_end]))
        return i

    def _check_fctl(self, img_bytes, index, exp_frame_num, exp_width, exp_height, exp_x_offset=0, exp_y_offset=0, exp_delay=32):
        i = index
        i, chunk_length = self._get_dword(img_bytes, i)
        self.assertEqual(chunk_length, 26)
        fctl_start = i
        i, chunk_type = self._get_chunk_type(img_bytes, i)
        self.assertEqual(FCTL, chunk_type)
        i, frame_num = self._get_dword(img_bytes, i)
        self.assertEqual(frame_num, exp_frame_num)
        i, width = self._get_dword(img_bytes, i)
        self.assertEqual(width, exp_width)
        i, height = self._get_dword(img_bytes, i)
        self.assertEqual(height, exp_height)
        i, x_offset = self._get_dword(img_bytes, i)
        self.assertEqual(x_offset, exp_x_offset)
        i, y_offset = self._get_dword(img_bytes, i)
        self.assertEqual(y_offset, exp_y_offset)
        i, delay_num = self._get_word(img_bytes, i)
        self.assertEqual(delay_num, exp_delay)
        i, delay_den = self._get_word(img_bytes, i)
        self.assertEqual(delay_den, 100)
        dispose_op = img_bytes[i]
        self.assertEqual(dispose_op, 0)
        i += 1
        blend_op = img_bytes[i]
        self.assertEqual(blend_op, 0)
        i += 1
        fctl_end = i
        i, fctl_crc = self._get_dword(img_bytes, i)
        self.assertEqual(fctl_crc, self._get_crc(img_bytes[fctl_start:fctl_end]))
        return i

    def _get_pixels_from_image_data(self, bit_depth, palette, image_data, width):
        if bit_depth == 4:
            scanline_len = (2 if width & 1 else 1) + width // 2
        elif bit_depth == 2:
            scanline_len = (2 if width & 3 else 1) + width // 4
        else:
            scanline_len = (2 if width & 7 else 1) + width // 8
        pixels = []
        for i, byte in enumerate(image_data):
            if i % scanline_len == 0:
                self.assertEqual(byte, 0)
                if i:
                    pixels.append(pixel_row[:width])
                pixel_row = []
            elif bit_depth == 4:
                pixel_row.append(palette[(byte & 240) // 16])
                pixel_row.append(palette[byte & 15])
            elif bit_depth == 2:
                for b in range(4):
                    pixel_row.append(palette[(byte & 192) // 64])
                    byte *= 4
            else:
                for b in range(8):
                    pixel_row.append(palette[(byte & 128) // 128])
                    byte *= 2
        pixels.append(pixel_row[:width])
        return pixels

    def _check_actl(self, img_bytes, index, exp_num_frames=2):
        i = index
        i, chunk_length = self._get_dword(img_bytes, i)
        actl_start = i
        i, chunk_type = self._get_chunk_type(img_bytes, i)
        self.assertEqual(ACTL, chunk_type)
        actl_end = i + chunk_length
        i, num_frames = self._get_dword(img_bytes, i)
        self.assertEqual(num_frames, exp_num_frames)
        i, repeat = self._get_dword(img_bytes, i)
        self.assertEqual(repeat, 0)
        i, actl_crc = self._get_dword(img_bytes, i)
        self.assertEqual(actl_crc, self._get_crc(img_bytes[actl_start:actl_end]))
        return i

    def _check_fdat(self, img_bytes, index, bit_depth, palette, exp_pixels, width, exp_seq_num=2):
        i = index
        i, chunk_length = self._get_dword(img_bytes, i)
        fdat_start = i
        i, chunk_type = self._get_chunk_type(img_bytes, i)
        self.assertEqual(FDAT, chunk_type)
        fdat_end = i + chunk_length
        i, seq_num = self._get_dword(img_bytes, i)
        self.assertEqual(seq_num, exp_seq_num)
        image_data_z = bytes(img_bytes[i:fdat_end])
        image_data = list(zlib.decompress(image_data_z))
        pixels = self._get_pixels_from_image_data(bit_depth, palette, image_data, width)
        self.assertEqual(len(pixels[0]), len(exp_pixels[0])) # width
        self.assertEqual(len(pixels), len(exp_pixels)) # height
        self.assertEqual(pixels, exp_pixels)
        i, fdat_crc = self._get_dword(img_bytes, fdat_end)
        self.assertEqual(fdat_crc, self._get_crc(img_bytes[fdat_start:fdat_end]))
        return i

    def _check_idat(self, img_bytes, index, bit_depth, palette, exp_pixels, width):
        i = index
        i, chunk_length = self._get_dword(img_bytes, i)
        idat_start = i
        i, chunk_type = self._get_chunk_type(img_bytes, i)
        self.assertEqual(IDAT, chunk_type)
        idat_end = i + chunk_length
        image_data_z = bytes(img_bytes[i:idat_end])
        image_data = list(zlib.decompress(image_data_z))
        pixels = self._get_pixels_from_image_data(bit_depth, palette, image_data, width)
        self.assertEqual(len(pixels[0]), len(exp_pixels[0])) # width
        self.assertEqual(len(pixels), len(exp_pixels)) # height
        self.assertEqual(exp_pixels, pixels)
        i, idat_crc = self._get_dword(img_bytes, idat_end)
        self.assertEqual(idat_crc, self._get_crc(img_bytes[idat_start:idat_end]))
        return i

    def _test_image(self, udg_array, scale=1, mask=0, x=0, y=0, width=None, height=None, iw_args=None, exp_pixels=None):
        image_writer = ImageWriter(**(iw_args or {}))
        img_bytes = self._get_image_data(image_writer, udg_array, 'png', scale, mask, x, y, width, height)

        exp_pixels2 = None
        if exp_pixels is None:
            exp_palette, has_trans, exp_pixels, exp_pixels2, frame2_xy = self._get_pixels_from_udg_array(udg_array, scale, mask, x, y, width, height)
            if not image_writer.options[PNG_ENABLE_ANIMATION]:
                exp_pixels2 = None
        else:
            exp_palette = []
            for row in exp_pixels:
                for pixel in row:
                    if pixel not in exp_palette:
                        exp_palette.append(pixel)
        palette_size = len(exp_palette)
        if palette_size > 4:
            exp_bit_depth = 4
        elif palette_size > 2:
            exp_bit_depth = 2
        else:
            exp_bit_depth = 1

        # PNG signature
        i = self._check_signature(img_bytes)

        # IHDR
        exp_width = 8 * scale * len(udg_array[0]) - x if width is None else width
        exp_height = 8 * scale * len(udg_array) - y if height is None else height
        i = self._check_ihdr(img_bytes, i, exp_width, exp_height, exp_bit_depth)

        # PLTE
        i, palette = self._check_plte(img_bytes, i, exp_palette)

        # tRNS
        alpha = image_writer.options[PNG_ALPHA]
        if alpha < 255 and has_trans:
            i = self._check_trns(img_bytes, i, alpha)

        # acTL and fcTL
        if exp_pixels2:
            i = self._check_actl(img_bytes, i)
            i = self._check_fctl(img_bytes, i, 0, exp_width, exp_height)

        # IDAT
        i = self._check_idat(img_bytes, i, exp_bit_depth, palette, exp_pixels, exp_width)

        # fcTL and fdAT
        if exp_pixels2:
            exp_width = len(exp_pixels2[0])
            exp_height = len(exp_pixels2)
            exp_x_offset, exp_y_offset = frame2_xy
            i = self._check_fctl(img_bytes, i, 1, exp_width, exp_height, exp_x_offset, exp_y_offset)
            i = self._check_fdat(img_bytes, i, exp_bit_depth, palette, exp_pixels2, exp_width)

        # IEND
        self.assertEqual(img_bytes[i:], IEND_CHUNK)

    def _test_animated_image(self, frames, iw_args=None):
        image_writer = ImageWriter(**(iw_args or {}))
        img_bytes = self._get_animated_image_data(image_writer, frames, 'png')

        exp_palette = []
        frame_data = []
        has_trans = 0
        for frame in frames:
            x, y, width, height = frame.x, frame.y, frame.width, frame.height
            frame_palette, f_has_trans, pixels, pixels2, frame2_xy = self._get_pixels_from_udg_array(frame.udgs, frame.scale, frame.mask, x, y, width, height)
            has_trans = has_trans or f_has_trans
            frame_data.append((width, height, pixels, frame.delay))
            for c in frame_palette:
                if c not in exp_palette:
                    exp_palette.append(c)

        palette_size = len(exp_palette)
        if palette_size > 4:
            exp_bit_depth = 4
        elif palette_size > 2:
            exp_bit_depth = 2
        else:
            exp_bit_depth = 1

        # PNG signature
        i = self._check_signature(img_bytes)

        # IHDR
        exp_width, exp_height = frame_data[0][:2]
        i = self._check_ihdr(img_bytes, i, exp_width, exp_height, exp_bit_depth)

        # PLTE
        i, palette = self._check_plte(img_bytes, i, exp_palette)

        # tRNS
        alpha = image_writer.options[PNG_ALPHA]
        if alpha < 255 and has_trans:
            i = self._check_trns(img_bytes, i, alpha)

        # acTL
        i = self._check_actl(img_bytes, i, len(frames))

        # Frames
        seq_num = 0
        for exp_width, exp_height, exp_pixels, exp_delay in frame_data:
            i = self._check_fctl(img_bytes, i, seq_num, exp_width, exp_height, exp_delay=exp_delay)
            seq_num += 1
            if seq_num == 1:
                i = self._check_idat(img_bytes, i, exp_bit_depth, palette, exp_pixels, exp_width)
            else:
                i = self._check_fdat(img_bytes, i, exp_bit_depth, palette, exp_pixels, exp_width, seq_num)
                seq_num += 1

        # IEND
        self.assertEqual(img_bytes[i:], IEND_CHUNK)

class GifWriterTest(SkoolKitTestCase, ImageWriterTest):
    def setUp(self):
        SkoolKitTestCase.setUp(self)
        self.animation_flag = GIF_ENABLE_ANIMATION
        self.alpha_option = {GIF_TRANSPARENCY: 1}

    def _get_word(self, stream, index):
        return index + 2, 256 * stream[index + 1] + stream[index]

    def _check_header(self, img_bytes):
        i = len(GIF_HEADER)
        self.assertEqual(img_bytes[:i], GIF_HEADER)
        return i

    def _check_lsd(self, img_bytes, index, exp_width, exp_height):
        i, width = self._get_word(img_bytes, index)
        self.assertEqual(width, exp_width)
        i, height = self._get_word(img_bytes, i)
        self.assertEqual(height, exp_height)
        return i

    def _check_gct(self, img_bytes, index, exp_palette):
        i, gct_flags = self._get_num(img_bytes, index)
        exp_palette_size = len(exp_palette)
        if exp_palette_size > 8:
            exp_gct_size = 3
        elif exp_palette_size > 4:
            exp_gct_size = 2
        elif exp_palette_size > 2:
            exp_gct_size = 1
        else:
            exp_gct_size = 0
        exp_gct_flags = 240 + exp_gct_size
        self.assertEqual(gct_flags, exp_gct_flags)
        i, bg_index = self._get_num(img_bytes, i)
        self.assertEqual(bg_index, 0)
        i, aspect_ratio = self._get_num(img_bytes, i)
        self.assertEqual(aspect_ratio, 0)
        gct = [img_bytes[j:j + 3] for j in range(i, i + 3 * exp_palette_size, 3)]
        self.assertEqual(sorted(exp_palette), sorted(gct))
        i += 3 * len(gct)
        full_gct_len = 1 << (1 + exp_gct_size)
        for n in range(full_gct_len - len(gct)):
            self.assertEqual(img_bytes[i:i + 3], [0, 0, 0])
            i += 3
        return i, gct

    def _check_gce(self, img_bytes, index, t_flag, delay):
        self.assertEqual(img_bytes[index:index + 8], [33, 249, 4, t_flag, delay, 0, 0, 0])
        return index + 8

    def _check_image_descriptor(self, img_bytes, index, exp_width, exp_height, exp_x_offset=0, exp_y_offset=0):
        i = index
        self.assertEqual(img_bytes[i], 44)
        i += 1
        i, x_offset = self._get_word(img_bytes, i)
        self.assertEqual(x_offset, exp_x_offset)
        i, y_offset = self._get_word(img_bytes, i)
        self.assertEqual(y_offset, exp_y_offset)
        i, width = self._get_word(img_bytes, i)
        self.assertEqual(width, exp_width)
        i, height = self._get_word(img_bytes, i)
        self.assertEqual(height, exp_height)
        i, lct = self._get_num(img_bytes, i)
        self.assertEqual(lct, 0)
        return i

    def _get_pixels_from_image_data(self, lzw_data, min_code_size, palette, width):
        num_clear_codes = 0
        clear_code = 1 << min_code_size
        stop_code = clear_code + 1
        init_d = {}
        for n in range(clear_code):
            init_d[n] = (n,)
        init_d[clear_code] = 0
        init_d[stop_code] = 0
        d = {}

        lzw_bits = deque()
        for lzw_byte in lzw_data:
            for j in range(8):
                lzw_bits.appendleft(lzw_byte & 1)
                lzw_byte >>= 1

        code_size = min_code_size + 1
        output = []
        prefix = None
        while 1:
            if len(lzw_bits) < code_size:
                self.fail('Unexpected end of LZW stream')

            # Collect a code from the LZW stream
            code = 0
            m = 1
            for k in range(code_size):
                code += m * lzw_bits.pop()
                m *= 2

            if code == clear_code:
                # Found a CLEAR code
                d = init_d.copy()
                code_size = min_code_size + 1
                prefix = None
                num_clear_codes += 1
                continue
            elif code == stop_code:
                # Found the STOP code
                break

            # Update the value of the last code added to the dictionary
            out = d[code]
            if out is None:
                out = prefix + prefix[0:1]
                d[code] = out
            elif prefix:
                d[len(d) - 1] = prefix + out[0:1]

            # Increase the code size if necessary
            if len(d) == 1 << code_size and len(lzw_bits) > code_size and code_size < 12:
                code_size += 1

            output.extend(out)
            prefix = out
            d[len(d)] = None

        pixels = [[]]
        for pixel in output:
            if len(pixels[-1]) == width:
                pixels.append([])
            pixels[-1].append(palette[pixel])
        return pixels, num_clear_codes

    def _check_image_data(self, img_bytes, index, width, height, palette, exp_min_code_size, exp_pixels, exp_clear_codes=None):
        i, min_code_size = self._get_num(img_bytes, index)
        self.assertEqual(min_code_size, exp_min_code_size)

        lzw_data = []
        while True:
            i, length = self._get_num(img_bytes, i)
            if length == 0:
                break
            lzw_data.extend(img_bytes[i:i + length])
            i += length

        pixels, num_clear_codes = self._get_pixels_from_image_data(lzw_data, min_code_size, palette, width)
        self.assertEqual(len(pixels[0]), len(exp_pixels[0])) # width
        self.assertEqual(len(pixels), len(exp_pixels)) # height
        self.assertEqual(exp_pixels, pixels)
        if exp_clear_codes is not None:
            self.assertEqual(num_clear_codes, exp_clear_codes)

        return i

    def _test_image(self, udg_array, scale=1, mask=0, x=0, y=0, width=None, height=None, iw_args=None, exp_pixels=None, exp_clear_codes=None):
        if iw_args is None:
            iw_args = {}
        options = iw_args.setdefault('options', {})
        image_writer = ImageWriter(**iw_args)
        img_bytes = self._get_image_data(image_writer, udg_array, 'gif', scale, mask, x, y, width, height)

        exp_pixels2 = None
        if exp_pixels is None:
            exp_palette, has_trans, exp_pixels, exp_pixels2, frame2_xy = self._get_pixels_from_udg_array(udg_array, scale, mask, x, y, width, height)
            if not image_writer.options[GIF_ENABLE_ANIMATION]:
                exp_pixels2 = None
        else:
            exp_palette = []
            for row in exp_pixels:
                for pixel in row:
                    if pixel not in exp_palette:
                        exp_palette.append(pixel)
            # Assume that there are transparent bits if mask is True
            has_trans = mask

        t_flag = 1 if image_writer.options[GIF_TRANSPARENCY] and has_trans else 0

        palette_size = len(exp_palette)
        if palette_size > 8:
            exp_min_code_size = 4
        elif palette_size > 4:
            exp_min_code_size = 3
        else:
            exp_min_code_size = 2

        # GIF header
        i = self._check_header(img_bytes)

        # Logical screen descriptor
        exp_width = 8 * scale * len(udg_array[0]) - x if width is None else width
        exp_height = 8 * scale * len(udg_array) - y if height is None else height
        i = self._check_lsd(img_bytes, i, exp_width, exp_height)

        # Global Colour Table
        i, palette = self._check_gct(img_bytes, i, exp_palette)

        # AEB and GCE (frame 1)
        if exp_pixels2:
            aeb_len = len(AEB)
            self.assertEqual(img_bytes[i:i + aeb_len], AEB)
            i += aeb_len
            i = self._check_gce(img_bytes, i, t_flag, GIF_FRAME_DELAY)
        elif t_flag:
            i = self._check_gce(img_bytes, i, t_flag, 0)

        # Frame 1 image descriptor
        i = self._check_image_descriptor(img_bytes, i, exp_width, exp_height)

        # Frame 1 image data
        i = self._check_image_data(img_bytes, i, exp_width, exp_height, palette, exp_min_code_size, exp_pixels, exp_clear_codes)

        # Frame 2
        if exp_pixels2:
            i = self._check_gce(img_bytes, i, t_flag, GIF_FRAME_DELAY)
            exp_width = len(exp_pixels2[0])
            exp_height = len(exp_pixels2)
            exp_x_offset, exp_y_offset = frame2_xy
            i = self._check_image_descriptor(img_bytes, i, exp_width, exp_height, exp_x_offset, exp_y_offset)
            i = self._check_image_data(img_bytes, i, exp_width, exp_height, palette, exp_min_code_size, exp_pixels2)

        # GIF trailer
        self.assertEqual(img_bytes[i], GIF_TRAILER)

    def _test_animated_image(self, frames, iw_args=None):
        if iw_args is None:
            iw_args = {}
        options = iw_args.setdefault('options', {})
        image_writer = ImageWriter(**iw_args)
        img_bytes = self._get_animated_image_data(image_writer, frames, 'gif')

        exp_palette = []
        frame_data = []
        has_trans = 0
        for frame in frames:
            x, y, width, height = frame.x, frame.y, frame.width, frame.height
            frame_palette, f_has_trans, pixels, pixels2, frame2_xy = self._get_pixels_from_udg_array(frame.udgs, frame.scale, frame.mask, x, y, width, height)
            has_trans = has_trans or f_has_trans
            frame_data.append((width, height, pixels, frame.delay))
            for c in frame_palette:
                if c not in exp_palette:
                    exp_palette.append(c)

        t_flag = 1 if image_writer.options[GIF_TRANSPARENCY] and has_trans else 0

        palette_size = len(exp_palette)
        if palette_size > 8:
            exp_min_code_size = 4
        elif palette_size > 4:
            exp_min_code_size = 3
        else:
            exp_min_code_size = 2

        # GIF header
        i = self._check_header(img_bytes)

        # Logical screen descriptor
        exp_width, exp_height = frame_data[0][:2]
        i = self._check_lsd(img_bytes, i, exp_width, exp_height)

        # Global Colour Table
        i, palette = self._check_gct(img_bytes, i, exp_palette)

        # AEB
        aeb_len = len(AEB)
        self.assertEqual(img_bytes[i:i + aeb_len], AEB)
        i += aeb_len

        # Frames
        for exp_width, exp_height, exp_pixels, exp_delay in frame_data:
            i = self._check_gce(img_bytes, i, t_flag, exp_delay)
            i = self._check_image_descriptor(img_bytes, i, exp_width, exp_height)
            i = self._check_image_data(img_bytes, i, exp_width, exp_height, palette, exp_min_code_size, exp_pixels)

        # GIF trailer
        self.assertEqual(img_bytes[i], GIF_TRAILER)

    def test_lzw_clear_code(self):
        pixels = ''.join(['{:b}'.format(n) for n in range(1639)]) + '0' * 17
        udgs = []
        index = 0
        while index < len(pixels):
            udg_data = [int(pixels[j:j + 8], 2) for j in range(index, index + 64, 8)]
            udgs.append(Udg((index // 64) & 127, udg_data))
            index += 64
        self._test_image([udgs], exp_clear_codes=2)

if __name__ == '__main__':
    unittest.main()
