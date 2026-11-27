import cv2
import numpy as np

from inputforge.vision.matcher import (
    TemplateCache,
    find_template,
    load_template,
    template_from_array,
)


def test_finds_exact_crop(screen):
    tpl = template_from_array(screen[300:340, 500:540].copy())
    m = find_template(screen, tpl, 0.95)
    assert m is not None
    assert (m.x, m.y, m.w, m.h) == (500, 300, 40, 40)
    assert m.center == (520, 320)
    assert m.score > 0.99


def test_tolerates_noise_and_grayscale(screen):
    crop = screen[100:150, 200:260].astype(np.int16)
    noisy = np.clip(crop + np.random.default_rng(1).integers(-20, 20, crop.shape), 0, 255)
    tpl = template_from_array(noisy.astype(np.uint8))
    assert find_template(screen, tpl, 0.85) is not None
    m = find_template(screen, tpl, 0.85, grayscale=True)
    assert m is not None and (m.x, m.y) == (200, 100)


def test_not_found(screen):
    other = np.random.default_rng(7).integers(0, 255, (30, 30, 3), dtype=np.uint8)
    assert find_template(screen, template_from_array(other), 0.9) is None


def test_template_larger_than_haystack():
    small = np.zeros((10, 10, 3), np.uint8)
    big = template_from_array(np.zeros((20, 20, 3), np.uint8))
    assert find_template(small, big, 0.5) is None


def test_alpha_mask_ignores_transparent_pixels(screen):
    crop = screen[400:440, 600:640].copy()
    bgra = cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
    bgra[:20, :, :3] = 0  # obere Hälfte „falsch“ …
    bgra[:20, :, 3] = 0  # … aber transparent
    tpl = template_from_array(bgra)
    assert tpl.mask is not None
    m = find_template(screen, tpl, 0.95)
    assert m is not None and (m.x, m.y) == (600, 400)


def test_load_and_cache(tmp_path, screen):
    path = tmp_path / "ümlaut icon.png"
    ok, buf = cv2.imencode(".png", screen[0:16, 0:16])
    assert ok
    path.write_bytes(buf.tobytes())
    tpl = load_template(path)
    assert tpl.size == (16, 16)
    cache = TemplateCache()
    assert cache.get(path) is cache.get(path)
