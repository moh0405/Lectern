import type { ReactNode, Ref } from "react";

export interface PageHeaderProps {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  /** Small mono uppercase line above the title (the desk's eyebrow), for example "404". */
  eyebrow?: ReactNode;
  /** Lets a page move focus to its heading (the heading becomes programmatically focusable). */
  headingRef?: Ref<HTMLHeadingElement>;
}

export function PageHeader({ title, description, actions, eyebrow, headingRef }: PageHeaderProps) {
  return (
    <header className="page-heading">
      <div>
        {eyebrow ? <p className="eyebrow page-heading-eyebrow">{eyebrow}</p> : null}
        <h1 ref={headingRef} tabIndex={headingRef ? -1 : undefined} className="page-heading-title">{title}</h1>
        {description ? <p className="page-heading-description">{description}</p> : null}
      </div>
      {actions}
    </header>
  );
}
