export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="page-container">
      <header className="page-header">
        <p className="eyebrow">Northstar Clinics</p>
        <h1>{title}</h1>
        <p>Prepared fictional operational evidence. No clinical decisions or real workflow actions.</p>
      </header>
    </div>
  );
}

