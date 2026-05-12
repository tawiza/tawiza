// Type augmentation for styled-jsx (bundled with Next.js but not exposed in
// the default React types). Adds the `jsx` and `global` boolean attributes
// on <style> elements so usages like `<style jsx global>{...}</style>` type-check.
import "react";

declare module "react" {
  interface StyleHTMLAttributes<T> extends HTMLAttributes<T> {
    jsx?: boolean;
    global?: boolean;
  }
}
