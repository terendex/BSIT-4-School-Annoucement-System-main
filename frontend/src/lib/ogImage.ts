/**
 * Builds the image Messenger and Facebook show in a link preview.
 *
 * Their card is roughly 1.91:1, and they *crop* whatever you give them to fit.
 * A portrait poster or a square graphic therefore loses its top and bottom -
 * exactly the part of an exam schedule or event poster that matters.
 *
 * Cloudinary can pad instead of crop, so the whole poster is visible with the
 * spare space filled in. That happens in the delivery URL, so there is no
 * re-upload and no extra work at request time.
 */

/** The aspect ratio Facebook and Messenger render a large card at. */
export const OG_WIDTH = 1200;
export const OG_HEIGHT = 630;

/**
 * c_pad  - scale to fit inside 1200x630 and pad the remainder, never cropping.
 * b_auto:predominant - fill the padding with the image's dominant colour, so
 *                      the bars read as part of the design rather than a border.
 * f_jpg  - force JPEG. Facebook handles it everywhere; f_auto could hand back
 *          AVIF/WebP, which its crawler has been inconsistent about.
 */
const OG_TRANSFORM = `c_pad,w_${OG_WIDTH},h_${OG_HEIGHT},b_auto:predominant,f_jpg`;

const CLOUDINARY_UPLOAD = "/image/upload/";

export interface OgImage {
  url: string;
  width: number | null;
  height: number | null;
  type: string | null;
}

/**
 * Returns the preview image for an announcement's cover photo.
 *
 * Non-Cloudinary URLs (the local-disk fallback used in development) are passed
 * through untouched - there is nothing to transform them with, and previews are
 * not testable from localhost anyway.
 */
export function ogImageFor(
  url: string,
  width: number | null,
  height: number | null,
  type: string | null
): OgImage {
  const marker = url.indexOf(CLOUDINARY_UPLOAD);
  if (!url.includes("res.cloudinary.com") || marker === -1) {
    return { url, width, height, type };
  }

  const head = url.slice(0, marker + CLOUDINARY_UPLOAD.length);
  const tail = url.slice(marker + CLOUDINARY_UPLOAD.length);
  return {
    url: `${head}${OG_TRANSFORM}/${tail}`,
    width: OG_WIDTH,
    height: OG_HEIGHT,
    type: "image/jpeg",
  };
}
