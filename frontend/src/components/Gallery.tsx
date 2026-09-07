import { useCallback, useEffect, useState } from "react";
import type { Attachment } from "../lib/types";

interface Props {
  images: Attachment[];
}

/** Image grid with a keyboard-navigable lightbox. */
export default function Gallery({ images }: Props) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const isOpen = openIndex !== null;

  const close = useCallback(() => setOpenIndex(null), []);
  const step = useCallback(
    (delta: number) =>
      setOpenIndex((current) =>
        current === null ? null : (current + delta + images.length) % images.length
      ),
    [images.length]
  );

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
      if (event.key === "ArrowRight") step(1);
      if (event.key === "ArrowLeft") step(-1);
    };
    document.addEventListener("keydown", onKey);
    // Stop the page behind the lightbox from scrolling.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [isOpen, close, step]);

  if (images.length === 0) return null;

  const active = openIndex === null ? null : images[openIndex];

  return (
    <>
      <ul className={images.length === 1 ? "gallery gallery--single" : "gallery"}>
        {images.map((image, index) => (
          <li key={image.id} className="gallery__item">
            <button
              type="button"
              className="gallery__button"
              onClick={() => setOpenIndex(index)}
              aria-label={`Open image ${index + 1}${image.caption ? `: ${image.caption}` : ""}`}
            >
              <img
                src={image.url}
                alt={image.caption || ""}
                width={image.width ?? undefined}
                height={image.height ?? undefined}
                loading="lazy"
                decoding="async"
              />
            </button>
            {image.caption && <p className="gallery__caption">{image.caption}</p>}
          </li>
        ))}
      </ul>

      {active && (
        <div
          className="lightbox"
          role="dialog"
          aria-modal="true"
          aria-label={active.caption || "Image viewer"}
          onClick={close}
        >
          <div className="lightbox__stage" onClick={(event) => event.stopPropagation()}>
            <img className="lightbox__image" src={active.url} alt={active.caption || ""} />
            {active.caption && <p className="lightbox__caption">{active.caption}</p>}
          </div>

          <button type="button" className="lightbox__close" onClick={close} aria-label="Close">
            &times;
          </button>

          {images.length > 1 && (
            <>
              <button
                type="button"
                className="lightbox__nav lightbox__nav--prev"
                onClick={(event) => {
                  event.stopPropagation();
                  step(-1);
                }}
                aria-label="Previous image"
              >
                &#8249;
              </button>
              <button
                type="button"
                className="lightbox__nav lightbox__nav--next"
                onClick={(event) => {
                  event.stopPropagation();
                  step(1);
                }}
                aria-label="Next image"
              >
                &#8250;
              </button>
              <p className="lightbox__counter">
                {openIndex! + 1} / {images.length}
              </p>
            </>
          )}
        </div>
      )}
    </>
  );
}
