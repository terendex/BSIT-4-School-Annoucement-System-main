import { useState } from "react";
import Modal from "./Modal";
import { ApiError } from "../../lib/adminClient";

interface Props {
  title: string;
  message: string;
  confirmLabel?: string;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
}

export default function ConfirmModal({
  title,
  message,
  confirmLabel = "Delete",
  onCancel,
  onConfirm,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const run = async () => {
    setBusy(true);
    setError("");
    try {
      await onConfirm();
    } catch (err) {
      setError((err as ApiError).message || "That did not work. Try again.");
      setBusy(false);
    }
  };

  return (
    <Modal
      title={title}
      onClose={onCancel}
      size="sm"
      busy={busy}
      footer={
        <>
          <button type="button" className="btn btn--ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button type="button" className="btn btn--danger" onClick={run} disabled={busy}>
            {busy ? "Working..." : confirmLabel}
          </button>
        </>
      }
    >
      {error && <p className="alert alert--error">{error}</p>}
      <p style={{ margin: 0 }}>{message}</p>
    </Modal>
  );
}
