import { redirect } from 'next/navigation';

export default function Home() {
  // Direct redirect to dashboard - no auth needed
  redirect('/dashboard');
}
