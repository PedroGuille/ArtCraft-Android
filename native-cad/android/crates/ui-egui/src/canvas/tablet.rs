//! Tablet gesture and pen taps share the canvas's normal point-picking path.
use super::{CadApp, Navigation, PointerInput, Vec2, Xf};

pub(super) fn input(app: &mut CadApp, ui: &egui::Ui, nav: &mut Navigation<'_>) -> (bool, bool, bool) {
    let p = &mut nav.pointer;
    let on_menu = p.hover_pos.is_some_and(|at| super::over_canvas_menu(app, at));
    app.session.ctrl_down = p.mods.ctrl;
    gesture(app, ui, nav.rect, nav.xf);
    let navigating = app.canvas.touch_navigation || (app.tablet_mode && app.canvas.tablet_pan);
    if !ui.input(|i| i.any_touches()) {
        app.canvas.touch_navigation = false;
    }
    p.pressed_primary &= !navigating;
    p.pressed_secondary &= !navigating;
    let pointer_inside = p.hover_pos.is_some_and(|at| nav.rect.contains(at) && ui.ctx().layer_id_at(at) == Some(ui.layer_id()))
        && (nav.response.hovered()
            || nav.response.clicked_by(egui::PointerButton::Primary)
            || nav.response.clicked_by(egui::PointerButton::Secondary));
    let mut inside = pointer_inside && !navigating;
    if app.tablet_mode {
        if let Some(pos) = p.hover_pos.filter(|_| pointer_inside && !on_menu) {
            app.canvas.tablet_cursor = Some(pos);
        }
        let tap = tap(app, ui, p, inside, navigating, nav.response.dragged_by(egui::PointerButton::Primary));
        if inside {
            p.pressed_primary = false;
        }
        match tap {
            crate::tablet::TapAction::Cancel => {
                app.session.cancel();
                app.cmd.buffer.clear();
                app.cmd.options = None;
                app.canvas.drag_window = false;
                app.canvas.hot_grips.clear();
            }
            crate::tablet::TapAction::Pick(pos, modifiers) => {
                p.hover_pos = Some(pos);
                p.mods = modifiers;
                inside = nav.rect.contains(pos);
                p.pressed_primary = inside;
            }
            crate::tablet::TapAction::None => {}
        }
    }
    (inside, on_menu, navigating)
}

fn gesture(app: &mut CadApp, ui: &egui::Ui, rect: egui::Rect, xf: Xf) {
    let touch = ui.input(|i| i.multi_touch());
    let Some(gesture) = touch.filter(|g| rect.contains(g.start_pos)) else { return };
    if app.tablet_mode && app.tablet_prefs.pen_only && app.canvas.tablet_pen_hover {
        return;
    }
    app.canvas.touch_navigation = true;
    if app.canvas.drag_window {
        app.session.pending_window = None;
        app.canvas.drag_window = false;
    }
    let delta = gesture.translation_delta;
    if delta.is_finite()
        && let Ok(st) = app.session.state_mut()
    {
        let view = st.view();
        st.set_view_quiet(cadcraft_engine::View {
            center: view.center - Vec2::new(f64::from(delta.x) / xf.scale, -f64::from(delta.y) / xf.scale),
            height: view.height,
        });
    }
    if gesture.zoom_delta.is_finite() && gesture.zoom_delta > 0.0 {
        let moved = Xf { center: app.session.state().map(|s| s.view().center).unwrap_or(xf.center), ..xf };
        let _ = app.session.zoom_about(f64::from(gesture.zoom_delta), moved.to_world(gesture.center_pos));
    }
}

fn tap(app: &mut CadApp, ui: &egui::Ui, p: &PointerInput, inside: bool, navigating: bool, dragging: bool) -> crate::tablet::TapAction {
    let precise = app.canvas.tablet_precise_pointer || app.canvas.tablet_pen_hover;
    let cancelled = ui.input(|i| {
        i.raw.events.iter().any(|e| {
            matches!(e, egui::Event::Key { key: egui::Key::Escape, pressed: true, .. })
                || (!precise && matches!(e, egui::Event::Touch { phase: egui::TouchPhase::Cancel, .. }))
        })
    });
    let barrel = app.tablet_prefs.barrel_cancel && inside && ui.input(|i| i.pointer.button_pressed(egui::PointerButton::Extra1));
    let blocked = cancelled
        || barrel
        || navigating
        || !ui.input(|i| i.focused)
        || app.ui.dialog.is_some()
        || egui::Popup::is_any_open(ui.ctx())
        || (p.pressed_primary && !inside)
        || p.pressed_secondary
        || dragging
        || p.scroll != egui::Vec2::ZERO
        || (ui.input(|i| i.zoom_delta()) - 1.0).abs() > 1e-4;
    let delay = app.tablet_prefs.double_tap_cancel && !(app.tablet_prefs.immediate_pen && precise);
    let doc = app.session.state().map_or(0, |s| s.uid);
    let command = app.session.running.as_ref().map(|r| r.id.as_str());
    let delayed = app.canvas.tablet_taps.update(
        ui.ctx(),
        doc,
        command,
        p.hover_pos.filter(|_| delay && inside && p.pressed_primary).map(|pos| (pos, p.mods)),
        delay && inside && p.dbl_primary,
        blocked || !delay,
    );
    if barrel {
        crate::tablet::TapAction::Cancel
    } else if !delay && !blocked && inside && p.pressed_primary {
        p.hover_pos.map_or(crate::tablet::TapAction::None, |pos| crate::tablet::TapAction::Pick(pos, p.mods))
    } else {
        delayed
    }
}
