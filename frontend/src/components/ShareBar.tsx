import { useEffect, useState } from "react";

interface Props {
  url: string;
  title: string;
}

/** Copy the shareable link, or hand it to Messenger / the native share sheet. */
export default function ShareBar({ url, title }: Props) {
  const [copied, setCopied] = useState(false);
  // Resolved after hydration so the server and client render the same markup.
  const [canShare, setCanShare] = useState(false);

  useEffect(() => setCanShare("share" in navigator), []);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      // Older browsers and non-secure contexts have no clipboard API.
      const field = document.createElement("textarea");
      field.value = url;
      field.setAttribute("readonly", "");
      field.style.position = "fixed";
      field.style.opacity = "0";
      document.body.appendChild(field);
      field.select();
      document.execCommand("copy");
      document.body.removeChild(field);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const share = async () => {
    if (navigator.share) {
      try {
        await navigator.share({ title, url });
        return;
      } catch {
        /* the user dismissed the sheet */
      }
    }
    void copy();
  };

  const messengerUrl = `https://www.facebook.com/dialog/send?link=${encodeURIComponent(
    url
  )}&app_id=0&redirect_uri=${encodeURIComponent(url)}`;

  return (
    <div className="sharebar">
      <button type="button" className="btn btn--sm" onClick={copy}>
        {copied ? "Link copied" : "Copy link"}
      </button>
      <a
        className="btn btn--sm btn--ghost"
        href={messengerUrl}
        target="_blank"
        rel="noopener noreferrer"
      >
        Send on Messenger
      </a>
      {canShare && (
        <button type="button" className="btn btn--sm btn--ghost" onClick={share}>
          Share
        </button>
      )}
      <code className="sharebar__url">{url}</code>
    </div>
  );
}
