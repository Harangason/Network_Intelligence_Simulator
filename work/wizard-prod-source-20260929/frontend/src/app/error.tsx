"use client";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="shell">
      <div className="panel error-card">
        <p className="eyebrow">Unerwarteter Fehler</p>
        <h1>Die Ansicht konnte nicht geladen werden.</h1>
        <button className="button primary" onClick={reset}>
          Erneut versuchen
        </button>
      </div>
    </main>
  );
}
