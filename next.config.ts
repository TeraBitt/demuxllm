import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  logging: {
    /**
     * Next forwards browser console output into the dev terminal. In practice
     * the loudest thing on that channel is other people's code — installed
     * Chrome extensions throw inside their own bundles on every page load, and
     * those rejections arrive here looking like application errors
     * (`chrome-extension://…/executors/200.js`), which they are not.
     *
     * Turned off, so the terminal shows the server and nothing else. The cost
     * is real and worth knowing: your own `console.log` from client components
     * no longer appears here either. Use the browser devtools console for
     * client-side debugging, or flip this to 'error' to get errors back.
     */
    browserToTerminal: false,
  },
};

export default nextConfig;
