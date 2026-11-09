import type { ReactNode } from "react";

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <header className="page-heading">
      <div>
        <h1 className="page-heading-title">{title}</h1>
        {description ? <p className="page-heading-description">{description}</p> : null}
      </div>
      {actions}
    </header>
  );
}
