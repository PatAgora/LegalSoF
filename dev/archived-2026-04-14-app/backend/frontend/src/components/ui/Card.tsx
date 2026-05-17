// CDD-style card. White surface, subtle border + 1px shadow, 6px radius.
//
// Composition:
//   <Card>
//     <Card.Header>…</Card.Header>
//     <Card.Body>…</Card.Body>
//     <Card.Footer>…</Card.Footer>
//   </Card>
//
// Header/Footer give the soft zinc-50/60 bands seen on the CDD app.
// Plain <Card> with bare children = full body padding, no banded
// header/footer.
import { HTMLAttributes, ReactNode } from 'react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  // Optional left-accent stripe for status emphasis. Kept available for
  // call sites that want it (matches CDD's accent border) but you can
  // ignore it — defaults to no accent.
  accent?: 'none' | 'zinc' | 'red' | 'amber' | 'green' | 'blue';
}

const ACCENT: Record<NonNullable<CardProps['accent']>, string> = {
  none:  '',
  zinc:  'border-l-2 border-l-zinc-400',
  red:   'border-l-2 border-l-red-500',
  amber: 'border-l-2 border-l-amber-500',
  green: 'border-l-2 border-l-green-500',
  blue:  'border-l-2 border-l-blue-500',
};

function CardRoot({ children, accent = 'none', className = '', ...rest }: CardProps) {
  return (
    <div
      className={`bg-white rounded-md border border-zinc-200/80 shadow-[0_1px_3px_0_rgb(0_0_0/0.04)] overflow-hidden ${ACCENT[accent]} ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}

function CardHeader({ children, className = '', ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`px-5 py-3 border-b border-zinc-100 bg-zinc-50/60 ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}

function CardBody({ children, className = '', ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`px-5 py-4 ${className}`} {...rest}>
      {children}
    </div>
  );
}

function CardFooter({ children, className = '', ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`px-5 py-3 border-t border-zinc-100 bg-zinc-50/60 ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}

const Card = Object.assign(CardRoot, {
  Header: CardHeader,
  Body: CardBody,
  Footer: CardFooter,
});

export default Card;
