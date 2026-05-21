// CDD-style table. Use the bare wrappers <Table>, <Thead>, <Tbody>,
// <Tr>, <Th>, <Td>. They apply the consistent zinc styling without
// trying to be a fully-featured datatable - call sites still own row
// content and sorting.
//
// Header row: bg-zinc-50/80, uppercase 11 px tracking-wider zinc-400.
// Body rows: white, hover bg-zinc-50/80, divide-y zinc-100.
import { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from 'react';

export function Table({ className = '', ...rest }: HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="overflow-x-auto border border-zinc-200/80 rounded-lg shadow-sm">
      <table className={`w-full ${className}`} {...rest} />
    </div>
  );
}

export function Thead({ className = '', ...rest }: HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={`bg-zinc-50/80 border-b border-zinc-200 ${className}`} {...rest} />;
}

export function Tbody({ className = '', ...rest }: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={`bg-white divide-y divide-zinc-100 ${className}`} {...rest} />;
}

export function Tr({ className = '', ...rest }: HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={`hover:bg-zinc-50/80 transition-colors duration-100 ${className}`} {...rest} />;
}

export function Th({ className = '', ...rest }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={`px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400 ${className}`}
      {...rest}
    />
  );
}

export function Td({ className = '', ...rest }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={`px-4 py-3 text-sm text-zinc-700 ${className}`} {...rest} />;
}
