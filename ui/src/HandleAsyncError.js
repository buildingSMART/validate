import { useCallback, useState } from 'react';

const HandleAsyncError = () => {
    const [_, setError] = useState();
    return useCallback(
      e => {
        setError(() => {
          throw e;
        });
      },
      [setError],
    );
  };
export default HandleAsyncError;
