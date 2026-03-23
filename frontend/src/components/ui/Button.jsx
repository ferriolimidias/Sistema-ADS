import Spinner from "./Spinner";

const VARIANT_CLASSES = {
  primary:
    "border border-transparent bg-blue-600 text-white hover:bg-blue-700 focus-visible:ring-blue-500",
  outline:
    "border border-slate-300 bg-white text-slate-700 hover:bg-slate-100 focus-visible:ring-slate-400",
  danger:
    "border border-transparent bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-500",
  ghost:
    "border border-transparent bg-transparent text-slate-700 hover:bg-slate-100 focus-visible:ring-slate-400",
};

const SIZE_CLASSES = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-4 text-sm",
  lg: "h-11 px-5 text-sm",
};

function cx(...classes) {
  return classes.filter(Boolean).join(" ");
}

export default function Button({
  variant = "primary",
  size = "md",
  isLoading = false,
  disabled = false,
  className = "",
  children,
  ...rest
}) {
  const isDisabled = disabled || isLoading;

  return (
    <button
      disabled={isDisabled}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-60",
        VARIANT_CLASSES[variant] || VARIANT_CLASSES.primary,
        SIZE_CLASSES[size] || SIZE_CLASSES.md,
        className
      )}
      {...rest}
    >
      {isLoading && <Spinner size={16} className="text-current" />}
      {isLoading ? "Processando..." : children}
    </button>
  );
}
