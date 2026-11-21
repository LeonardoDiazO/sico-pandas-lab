---
title: 'Story 11.2: Feedback distinto al superar un reto'
type: 'feature'
created: '2026-09-23'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
baseline_commit: '8b18250'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `guided-lesson.component` ya distingue "reto superado" de "reto fallido" (el backend ya manda `challengeVerdict.passed`, booleano) y ya pinta un aviso con color distinto (`.verdict.passed`/`.failed`) — pero es estático: mismo tratamiento visual que cualquier aviso, sin transición ni realce que haga sentir el logro. Además, como el resto del módulo guiado, sus colores están hardcodeados en hex, no en los design tokens compartidos.

**Approach:** Agregar una animación de entrada CSS (`@keyframes`, respetando `prefers-reduced-motion` — mismo patrón ya usado en `no-code-home`/`column-classification`) solo a `.verdict.passed`, con un ✓ más grande y un realce de borde — sin tocar `.failed`, que se queda exactamente como está hoy ("si el código corre sin error pero no cumple el reto, veo el resultado normal", AC explícito). De paso, migrar los colores de `.verdict` (ambos estados) a los tokens `--ok`/`--ok-soft`/`--ok-border` y `--bad`/`--bad-soft`/`--bad-border`, como pide la épica para cualquier color que se toque en este módulo. No se modifica `challenge_id`/lógica de verificación del backend, ni el selector `.challenge` que referencia el tour guiado (`guided-tour-steps.ts`).

</frozen-after-approval>

## Implementation Notes

- `guided-lesson.component.html`: el bloque `.verdict` ahora envuelve el ícono y el mensaje en `<span>` separados (`.verdict-icon`/`.verdict-message`) para poder agrandar solo el ícono en el estado `.passed`.
- `guided-lesson.component.scss`: `@keyframes verdict-passed-in` (fade + scale + translateY sutil) aplicado solo a `.verdict.passed`, con guard `@media (prefers-reduced-motion: reduce)` (mismo patrón que `no-code-home`/`column-classification`). `.failed` no cambia de comportamiento, solo de fuente de color (migrado a tokens). Colores de ambos estados migrados a `--ok`/`--ok-soft`/`--ok-border` y `--bad`/`--bad-soft`/`--bad-border`, con fallback al hex anterior.
- No se tocó `guided-lesson.component.ts` ni el selector `.challenge` que referencia `guided-tour-steps.ts`.
- `yarn build` limpio.
- **Sin test agregado**: el módulo guiado no tiene ningún spec existente (`guided/**/*.spec.ts` está vacío hoy) y `GuidedLessonComponent` inyecta 5 servicios (`GuidedService`, `NotebookService`, `UserProfileService`, `TourService`, `ActivatedRoute`) más varios componentes hijo en su plantilla — levantar un harness de test completo para este cambio de CSS/plantilla es desproporcionado al alcance de esta historia. Documentado como trabajo diferido en `deferred-work.md`.
- Revisión (blind-hunter): 7 hallazgos, 5 sobreviven, parchados en el mismo pase (1 diferido, 1 rechazado):
  - `.banner.ok`/`.banner.bad`/`.done` (mismo archivo, mismo tipo de aviso) migrados a los mismos tokens que `.verdict` — antes convivían dos tonos distintos de "verde éxito"/"rojo error" en la misma pantalla.
  - `runChallenge()` ahora reinicia `challengeVerdict = null` al empezar — sin esto, un reintento ya-aprobado nunca vuelve a disparar la animación de entrada (el bloque `@if` nunca sale del DOM entre intentos).
  - `role="status"` en `.verdict` (implica `aria-live="polite"`) y `aria-hidden="true"` en el ícono emoji — antes no había anuncio para lectores de pantalla ni se evitaba la lectura redundante del emoji.
  - `align-items: center` → `flex-start` en `.verdict` — evita que el ícono quede mal alineado si el mensaje (controlado por el backend) envuelve a 2+ líneas.
  - Fallbacks de color corregidos a los valores reales actuales de los tokens (`--ok-soft: #e6f6ee`, `--ok: #1a7a4c`, `--bad-soft: #fdeceb`, `--bad: #b23a2f`), no a los hex viejos pre-migración.
  - Diferido: falta de cobertura de test para este componente (ver `deferred-work.md`) — el fix real (harness completo) no es trivial.
  - Rechazado: asimetría de tamaño del ícono (1.3rem en `.passed` vs 0.88rem heredado en `.failed`) — es intencional y está documentado en el Intent de esta spec (`.failed` se queda exactamente como estaba), no un descuido.

## Review Triage Log

| # | Hallazgo | Veredicto | Evidencia |
|---|----------|-----------|-----------|
| 1 | `.banner`/`.done` (mismo archivo) seguían en hex viejo, distinto tono que `.verdict` ya migrado | medium | Real y visible en la misma pantalla. Patch (migrados también). |
| 2 | Reintento tras ya-aprobado no repite la animación (`challengeVerdict` nunca se resetea) | medium | Real: rompe el propósito central de la historia en un caso de uso plausible. Patch. |
| 3 | Sin `aria-live`/`role`, emoji no `aria-hidden` | low | Real hueco de accesibilidad, fix trivial. Patch. |
| 4 | Asimetría de tamaño del ícono entre `.passed`/`.failed` | false | Intencional y documentado en el Intent de esta misma spec — `.failed` debía quedarse exactamente igual. |
| 5 | `align-items: center` no robusto ante mensajes multilínea | low | Real, plausible (mensaje viene del backend sin límite de longitud). Patch. |
| 6 | Fallbacks de color congelados al hex pre-migración, no al valor real del token | low | Real, mismo patrón que Story 10.5. Patch (fallbacks corregidos). |
| 7 | Sin cobertura de test para el cambio | — | Real, pero el fix (harness completo para un componente con 5 servicios inyectados) no es trivial. Diferido en `deferred-work.md`. |

