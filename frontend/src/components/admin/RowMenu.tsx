import { useEffect, useLayoutEffect, useRef, useState } from "react";

export interface RowAction {
  label: string;
  onSelect: () => void;
  /** Rendered in red, and set apart at the foot of the menu. */
  danger?: boolean;
}

interface Props {
  /** Names the row this menu belongs to, for screen readers. */
  label: string;
  actions: RowAction[];
}

/**
 * The actions for one row, behind a single button.
 *
 * Five buttons spread across a row pushed the table past the width of the
 * page and left the columns colliding. One button opens them as a list
 * instead, which also scales: a sixth action costs nothing here.
 *
 * The panel is positioned fixed rather than dropped inside the cell, because
 * the table sits in a horizontal scroller and anything absolutely positioned
 * within it is clipped at the edge.
 */
export default function RowMenu({ label, actions }: Props) {
  const [open, setOpen] = useState(false);
  const [at, setAt] = useState({ top: 0, left: 0 });
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const close = (returnFocus = true) => {
    setOpen(false);
    if (returnFocus) buttonRef.current?.focus();
  };

  // Positioned once the panel exists, so its real height decides whether it
  // opens downwards or flips up at the bottom of the window.
  useLayoutEffect(() => {
    if (!open) return;
    const button = buttonRef.current;
    const panel = panelRef.current;
    if (!button || !panel) return;

    const rect = button.getBoundingClientRect();
    const height = panel.offsetHeight;
    const width = panel.offsetWidth;
    const room = window.innerHeight - rect.bottom;

    setAt({
      top: room < height + 12 ? Math.max(8, rect.top - height - 6) : rect.bottom + 6,
      left: Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8)),
    });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    panelRef.current?.querySelector<HTMLElement>("button")?.focus();

    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!panelRef.current?.contains(target) && !buttonRef.current?.contains(target)) {
        close(false);
      }
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        close();
        return;
      }
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;

      const items = [...(panelRef.current?.querySelectorAll<HTMLElement>("button") ?? [])];
      if (items.length === 0) return;
      event.preventDefault();
      const here = items.indexOf(document.activeElement as HTMLElement);
      const step = event.key === "ArrowDown" ? 1 : -1;
      items[(here + step + items.length) % items.length].focus();
    };

    // The panel is anchored to where the button was, so it follows neither a
    // scroll nor a resize - it closes instead.
    const onMove = () => close(false);

    document.addEventListener("pointerdown", onPointerDown, true);
    document.addEventListener("keydown", onKeyDown, true);
    window.addEventListener("scroll", onMove, true);
    window.addEventListener("resize", onMove);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown, true);
      document.removeEventListener("keydown", onKeyDown, true);
      window.removeEventListener("scroll", onMove, true);
      window.removeEventListener("resize", onMove);
    };
  }, [open]);

  const ordinary = actions.filter((action) => !action.danger);
  const destructive = actions.filter((action) => action.danger);

  const item = (action: RowAction) => (
    <button
      key={action.label}
      type="button"
      role="menuitem"
      className={`row-menu__item${action.danger ? " row-menu__item--danger" : ""}`}
      onClick={() => {
        close(false);
        action.onSelect();
      }}
    >
      {action.label}
    </button>
  );

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        className="btn btn--sm btn--ghost row-menu"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Actions for ${label}`}
        onClick={() => (open ? close() : setOpen(true))}
      >
        &#8943;
      </button>

      {open && (
        <div
          ref={panelRef}
          className="row-menu__panel"
          role="menu"
          aria-label={`Actions for ${label}`}
          style={{ top: `${at.top}px`, left: `${at.left}px` }}
        >
          {ordinary.map(item)}
          {destructive.length > 0 && ordinary.length > 0 && (
            <span className="row-menu__rule" aria-hidden="true" />
          )}
          {destructive.map(item)}
        </div>
      )}
    </>
  );
}
