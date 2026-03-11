import { Card } from './ui/card';
import ReactMarkdown from 'react-markdown';

export default function MessageBox(props: { output: string }) {
  const { output } = props;
  return (
    <Card className="mb-7 flex min-h-[564px] w-full min-w-fit rounded-lg border px-5 py-4 font-medium dark:border-zinc-800">
      <div className="font-medium dark:text-white">
        <ReactMarkdown>
          {output ? output : 'Your generated response will appear here...'}
        </ReactMarkdown>
      </div>
    </Card>
  );
}
