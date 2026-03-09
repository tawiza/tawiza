export const getURL = (path?: string) => {
  let url =
    process?.env?.NEXT_PUBLIC_SITE_URL ??
    process?.env?.NEXT_PUBLIC_VERCEL_URL ??
    'http://localhost:3000/';
  url = url.includes('http') ? url : `https://${url}`;
  url = url.charAt(url.length - 1) === '/' ? url : `${url}/`;

  if (path) {
    path = path.replace(/^\/+/, '');
    return path ? `${url}/${path}` : url;
  }

  return url;
};

export const postData = async ({
  url,
  data,
}: {
  url: string;
  data?: Record<string, unknown>;
}) => {
  const res = await fetch(url, {
    method: 'POST',
    headers: new Headers({ 'Content-Type': 'application/json' }),
    credentials: 'same-origin',
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    console.error('Error in postData', { url, data, res });
    throw Error(res.statusText);
  }

  return res.json();
};

export const toDateTime = (secs: number) => {
  const t = new Date('1970-01-01T00:30:00Z');
  t.setSeconds(secs);
  return t;
};

export const formatDate = (date: Date): string => {
  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
};

export const formatNumber = (num: number): string => {
  return new Intl.NumberFormat('fr-FR').format(num);
};
