import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import styles from "./Field.module.css";

function FieldShell({
  label,
  hint,
  children,
}: {
  label: ReactNode;
  hint?: ReactNode;
  children: ReactNode;
}) {
  return (
    <label className={styles.field}>
      <span className={styles.label}>{label}</span>
      {children}
      {hint && <span className={styles.hint}>{hint}</span>}
    </label>
  );
}

type InputFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: ReactNode;
  hint?: ReactNode;
};

export function InputField({ label, hint, className, ...rest }: InputFieldProps) {
  return (
    <FieldShell label={label} hint={hint}>
      <input className={[styles.control, className].filter(Boolean).join(" ")} {...rest} />
    </FieldShell>
  );
}

type TextareaFieldProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: ReactNode;
  hint?: ReactNode;
};

export function TextareaField({ label, hint, className, ...rest }: TextareaFieldProps) {
  return (
    <FieldShell label={label} hint={hint}>
      <textarea className={[styles.control, className].filter(Boolean).join(" ")} {...rest} />
    </FieldShell>
  );
}

type SelectFieldProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label: ReactNode;
  hint?: ReactNode;
};

export function SelectField({ label, hint, className, children, ...rest }: SelectFieldProps) {
  return (
    <FieldShell label={label} hint={hint}>
      <select className={[styles.control, className].filter(Boolean).join(" ")} {...rest}>
        {children}
      </select>
    </FieldShell>
  );
}
