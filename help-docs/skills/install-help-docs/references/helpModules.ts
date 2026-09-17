// Destination: <appSrc>/utils/helpModules.ts
// Which optional parts of the application are switched on, for the help documentation.
// Design: docs/specs/2026-09-17-help-modules.md section 6.1 (in the help-docs plugin's repository).
//
// Content marked with a module -- `module:` in a document's frontmatter, or a `:::module` block
// inside one -- is shown only when that module's predicate returns true. Everything else is
// always visible, so an application with no optional parts leaves this file exactly as it is.
//
// THIS IS THE ONE FILE OF THE HELP SYSTEM THE APPLICATION IS EXPECTED TO EDIT. The rest can be
// replaced wholesale when the help system is updated; this holds the wiring that is yours.
//
// The module names come from `docs/help/modules.json`, which the generator turns into the
// `HelpModuleName` union. That is what keeps the two in step: a declared module with no
// predicate here, or a predicate for a name that is not declared, fails `typecheck` rather than
// silently hiding documentation.
//
// Predicates are called during rendering, not cached, so whatever reactive source they read is
// tracked by the surrounding computed -- a store getter, a composable, a `useState`. Keep them
// cheap and free of side effects.
//
// A filled-in example, for an application whose GDPR features hang off a backend setting:
//
//     import { useRootStore } from '~/store'
//
//     export const helpModuleFlags: Record<HelpModuleName, () => boolean> = {
//         gdpr: () => useRootStore().appSettings?.use_gdpr === true,
//     }
//
// Remember that hiding a document is not access control: the content is still in the bundle the
// browser downloaded. It keeps the documentation relevant, not secret.
import type { HelpModuleName } from '~/help/generated/manifest'

export const helpModuleFlags: Record<HelpModuleName, () => boolean> = {}
