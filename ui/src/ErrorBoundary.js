import { useState } from 'react';

export default function ErrorBoundary({ children }) {
  const [hasError, setHasError] = useState(false);

  function handleOnError() {
    setHasError(true);
  }

  return hasError ? <div>Oops! Something went wrong.</div> : (
    <div onError={handleOnError}>
      {children}
    </div>
  );
}