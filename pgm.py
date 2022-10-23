from enum import Enum
from functools import reduce
from sys import argv, exit
import pygame
import argparse
import os
import glob
from PIL import Image
from itertools import cycle


def is_image(path):
    path = path.lower()
    return path.endswith('.png') or path.endswith('.jpg')


def has_transparency(image):
    return image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info)


class ColorCodes(Enum):
    RED = 255, 0, 0
    GREEN = 0, 255, 0
    BLUE = 0, 0, 255
    WHITE = 255, 255, 255
    BLACK = 0, 0, 0
    MAGENTA = 255, 0, 255

    @classmethod
    def values(cls):
        return [code.name for code in cls]


def bg_color_validate(bg_color):
    if type(bg_color) is str:
        bg_color = bg_color.upper()
        if bg_color in ColorCodes.values():
            return ColorCodes[bg_color].value
    if len(bg_color) == 3:
        return bg_color

    raise ValueError(f'Color is not valid {bg_color}')


def replace_transparency(image, bg_colour=(255, 0, 255)):
    """
    Based on https://stackoverflow.com/questions/35859140/remove-transparency-alpha-from-any-image-using-pil
    """
    # Need to convert to RGBA if LA format due to a bug in PIL (http://stackoverflow.com/a/1963146)
    alpha = image.convert('RGBA').split()[-1]

    # Create a new background image of our matt color.
    # Must be RGBA because paste requires both images have the same format
    # (http://stackoverflow.com/a/8720632  and  http://stackoverflow.com/a/9459208)
    bg = Image.new("RGBA", image.size, bg_colour + (255,))
    bg.paste(image, mask=alpha)
    return bg


def make_crop_box(index, grid_columns, tile_size):
    top_left = tile_size[0] * (index % grid_columns), tile_size[1] * (index // grid_columns)
    return top_left[0], top_left[1], top_left[0] + tile_size[0], top_left[1] + tile_size[1]


def load_images_from_dir(dir_path):
    # open and filter out images that are not images
    images = [Image.open(path) for path in glob.glob(f"{dir_path}/*") if is_image(path)]
    if len(images) <= 0:
        raise FileNotFoundError(f'No images in dir: {dir_path}')

    # check if all images have the same size
    img_size = images[0].width, images[0].height
    validated = reduce(lambda a, b: a and (b.width, b.height) == img_size, images[1:], True)
    if not validated:
        raise ValueError(f'Image sizes are not equal to first image: {img_size}.')

    return images


def load_images_from_tileset(tileset_path, grid_size, start_index, frames_count, bg_color):
    if not is_image(tileset_path):
        raise ValueError(f"File {tileset_path} is not image.")

    end_index = start_index + frames_count
    tileset_image = Image.open(tileset_path)
    if has_transparency(tileset_image):
        tileset_image = replace_transparency(tileset_image, bg_color)
    tile_size = tileset_image.width // grid_size[0], tileset_image.height // grid_size[1]
    images = [tileset_image.crop(make_crop_box(index, grid_size[0], tile_size)) for index in
              range(start_index, end_index)]

    return images


def save_temp_images(images, temp_dir_path='frames'):
    if not os.path.isdir(temp_dir_path):
        os.mkdir(temp_dir_path)
    else:
        content = [os.path.join(temp_dir_path, filename) for filename in os.listdir(temp_dir_path)]
        for path_to_remove in content:
            os.remove(path_to_remove)
    for idx, image in enumerate(images):
        image.save(os.path.join(temp_dir_path, f"{idx}.png"))


def make_gif(frames, gif_name, duration_s):
    frame_one = frames[0]
    frame_one.save(gif_name, format="GIF", append_images=frames[1:], save_all=True,
                   duration=duration_s * 1000 // len(frames), loop=0)


def build_from_series(path):
    if os.path.isdir(path):
        return load_images_from_dir(path)
    raise NotADirectoryError(f"{path}")


def build_from_tileset(path, grid_size, start_index, frames_count, bg_color):
    if frames_count == 0:
        raise ValueError('Set frames_count to more than 0.')
    bg_color = bg_color_validate(bg_color)

    if not os.path.isdir(path):
        return load_images_from_tileset(path, grid_size, start_index, frames_count, bg_color)
    raise FileExistsError(f"Should be directory {path}")


def preview(images, interval, img_size, preview_width):
    pygame.init()
    scale = preview_width/img_size[0]
    preview_size = img_size[0] * scale, img_size[1] * scale
    window = pygame.display.set_mode(preview_size)
    # convert and scale preview
    surfaces = (pygame.image.fromstring(i.tobytes(), i.size, i.mode) for i in images)
    surfaces = [pygame.transform.scale(i, preview_size) for i in surfaces]
    cycler = cycle(surfaces)
    clock = pygame.time.Clock()

    while True:
        clock.tick(1 / interval)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                exit(0)
        if pygame.key.get_pressed()[pygame.K_ESCAPE]:
            exit(0)

        surface = next(cycler)

        window.fill(0)
        window.blit(surface, surface.get_rect(topleft=(0, 0)))
        pygame.display.flip()


if __name__ == '__main__':
    app_name = 'Python Gif Maker'
    dsc = """Create gif files from series of images or tileset."""

    # mode selector
    args = argv[1:]
    mode_selector = argparse.ArgumentParser(prog=app_name, description=dsc)
    mode_selector.add_argument('mode', choices=['series', 'tileset'], default='series')
    mode_parsed = mode_selector.parse_args(args=args[:1]).mode

    # build params
    args = args[1:]
    # print(args)
    build_parser = argparse.ArgumentParser(prog=f"{app_name} - {mode_parsed}")
    build_parser.add_argument('path', type=str)
    build_parser.add_argument('-d', '--duration', type=float, default=1.0)
    build_parser.add_argument('-p', '--preview_width', type=int, default=-1)
    build_parser.add_argument('-o', '--output_name', default='out.gif')
    build_parser.add_argument('-t', '--temp_save', action='store_true')
    build_parser.add_argument('-w', '--width', type=int, default=-1)

    if mode_parsed == 'series':
        build_parser.description = "Build gif from series of images."
        p = build_parser.parse_args(args=args)
        images = build_from_series(p.path)
    else:
        build_parser.description = "Build gif from tileset indices."
        build_parser.add_argument('-g', '--gridsize', type=int, nargs=2, default=[2, 2])
        build_parser.add_argument('-s', '--start_index', type=int, default=0)
        build_parser.add_argument('-f', '--frames_count', type=int, default=4)
        build_parser.add_argument('-b', '--bg_color', type=str, choices=ColorCodes.values(), default='MAGENTA')
        p = build_parser.parse_args(args=args)
        images = build_from_tileset(p.path, p.gridsize, p.start_index, p.frames_count, p.bg_color)

    if not p.output_name.lower().endswith('gif'):
        p.output_name = p.output_name + '.gif'

    if p.temp_save:
        save_temp_images(images)

    make_gif(images, p.output_name, p.duration)

    if p.preview_width > -1:
        img_size = images[0].width, images[0].height
        preview(images, p.duration / len(images), img_size, p.preview_width)
