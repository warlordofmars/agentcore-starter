// Copyright (c) 2026 John Carter. All rights reserved.
import * as React from "react";
import { Toaster as SonnerToaster } from "sonner";

function Toaster(props) {
  return <SonnerToaster theme="system" richColors {...props} />;
}

export { Toaster };
