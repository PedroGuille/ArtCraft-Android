use super::viewport::{split_viewport, stencil_clip};
use super::{Arc, Geometry, Scene};
use super::{Bounds2, CadApp, DisplayList, Handle, ListKey, Rgb, Tokens, Vec2, Xf, rebuild, same_content};

/// Primitives of `list` sorted by entity handle, built on the first highlight after each list
/// rebuild. Highlighting the hovered entity used to scan every primitive on every frame: ~2.5 ms
/// per frame on a 270k-entity drawing, whether or not anything changed.
#[derive(Default)]
pub(super) struct PrimIndex {
    list_gen: Option<u64>,
    by_handle: Vec<(Handle, usize)>,
}

impl PrimIndex {
    /// Indices of the primitives drawn for `handles` (in list order).
    pub(super) fn prims(&mut self, list_gen: u64, list: &impl Geometry, handles: &[Handle]) -> Vec<usize> {
        if handles.is_empty() {
            return Vec::new();
        }
        if self.list_gen != Some(list_gen) {
            self.by_handle = list.primitives().enumerate().map(|(i, p)| (p.prim.handle, i)).collect();
            self.by_handle.sort_unstable();
            self.list_gen = Some(list_gen);
        }
        let mut out = Vec::new();
        for h in handles {
            let from = self.by_handle.partition_point(|(k, _)| k < h);
            out.extend(self.by_handle.get(from..).unwrap_or(&[]).iter().take_while(|(k, _)| k == h).map(|(_, i)| *i));
        }
        out.sort_unstable();
        out.dedup();
        out
    }
}

/// Indices of the primitives in `list` drawn for `handles` (a scan: the reference [`PrimIndex`]
/// is tested against).
#[cfg(test)]
pub(super) fn prims_of(list: &DisplayList, handles: &[Handle]) -> Vec<usize> {
    if handles.is_empty() {
        return Vec::new();
    }
    let set: std::collections::HashSet<Handle> = handles.iter().copied().collect();
    list.prims.iter().enumerate().filter(|(_, pr)| set.contains(&pr.handle)).map(|(i, _)| i).collect()
}

/// Build options for previews at `scale` pixels per drawing unit (opaque).
pub(super) fn preview_options(scale: f64) -> cadcraft_render::Options {
    cadcraft_render::Options { tolerance: 0.5 / scale, min_dash: 2.0 / scale, ..Default::default() }
}

/// The display list of preview entities the session builds with the current properties
/// ([`cadcraft_engine::Session::preview`], the extras of [`cadcraft_engine::Session::drag`]): the
/// command's rubber band and rebuilt copies of existing objects. They carry CLAYER's properties,
/// not the objects', so they are drawn opaque (the GPU drag of the objects themselves keeps their
/// transparency, see [`draw_drag_gpu`]).
pub(super) fn rebuilt_preview<'a>(doc: &cadcraft_doc::Drawing, ents: impl IntoIterator<Item = &'a cadcraft_doc::Entity>, scale: f64) -> DisplayList {
    cadcraft_render::build_entities(doc, ents, &preview_options(scale))
}

/// Rebuild the display list when needed. `xf`: the current view; `views`: every area on screen
/// that shows the list (the current view, other model tiles) with its drawing units per pixel.
///
/// A rebuild only the view asks for (a new zoom band, a pan out of the built area) runs in the
/// background while the current list is drawn (see [`rebuild`]); a changed drawing, or no list
/// yet, is built at once.
/// The font set text is drawn with: TrueType fonts (font folders, rescans) and SHX fonts
/// (drawing folders, font folders, the search path) can each change what text looks like. Every
/// cache of drawn geometry keys on it.
pub(super) fn font_generation() -> u64 {
    cadcraft_fonts::ttf::generation().wrapping_add(cadcraft_fonts::shx::generation() << 32)
}

pub(super) fn ensure_list(app: &mut CadApp, xf: &Xf, views: &[(Bounds2, f64)], ctx: &egui::Context) {
    app.canvas.render_cache.set_spatial_partition(app.tablet_mode);
    let now = ctx.input(|i| i.time);
    let current = app.canvas.xf.map_or((xf.center, xf.scale), |active| (active.center, active.scale));
    if app.tablet_mode && app.canvas.navigation_view.is_some_and(|old| old != current) {
        app.canvas.navigation_until = now + 0.18;
    }
    app.canvas.navigation_view = Some(current);
    let navigation = app.tablet_mode && now < app.canvas.navigation_until;
    app.canvas.navigation_active = navigation;
    app.canvas.reduced_navigation_resolution = app.tablet_prefs.reduced_navigation_resolution;
    app.canvas.navigation_fps = app.tablet_prefs.navigation_fps;
    if navigation {
        ctx.request_repaint_after(std::time::Duration::from_secs_f64((app.canvas.navigation_until - now).max(0.001)));
    }
    let px = 1.0 / xf.scale;
    let fonts = font_generation();
    if app.canvas.font_generation != fonts {
        app.canvas.font_generation = fonts;
        app.canvas.list = None;
        app.canvas.job = None;
        // The model space seen through a layout's active viewport is drawn apart: rebuilt too.
        app.canvas.vp.key = None;
    }
    let Ok(st) = app.session.state() else { return };
    // Rebuild when the drawing changes, the zoom moves by more than 2x (tessellation band) or a
    // view leaves the area the list was built for.
    let band = |px: f64| px.max(1e-300).log2().floor() as i32;
    // Hatch level of detail follows the finest view showing the list.
    let lod_band = views.iter().map(|v| band(v.1)).fold(band(px), i32::min);
    let curve_band = band(px);
    // The active MSPACE viewport's contents are drawn apart (see `VpContent`), so panning and
    // zooming inside it leave this list alone. Without a stencil buffer a clipped viewport's
    // contents stay in the list, which then follows its view: realtime navigation changes it
    // without a new revision.
    let split = split_viewport(st, stencil_clip(app)).map(|(h, ..)| h);
    let vp_view = {
        use std::hash::{Hash, Hasher};
        let mut s = std::collections::hash_map::DefaultHasher::new();
        split.hash(&mut s);
        if split.is_none()
            && let Some((h, vp)) = st.active_viewport()
        {
            (h, vp.view_center.x.to_bits(), vp.view_center.y.to_bits(), vp.view_height.to_bits()).hash(&mut s);
        }
        s.finish()
    };
    let (lwdisplay, transparency_display) = (app.session.settings.lwdisplay, app.session.settings.transparency_display);
    let key: ListKey = (
        st.uid,
        st.revision,
        curve_band,
        lod_band,
        lwdisplay,
        transparency_display,
        std::sync::Arc::as_ptr(&st.doc) as usize,
        vp_view,
        cadcraft_render::screen::font_revision(),
    );
    app.canvas.scenes.retain(|s| app.session.docs.iter().any(|d| d.uid == s.key.0));
    if app.canvas.key.0 != st.uid || app.canvas.space != st.space {
        app.canvas.job = None;
        if let (Some(list), Some(source)) = (app.canvas.list.take(), app.canvas.source.take()) {
            app.canvas.scenes.push_back(Scene {
                key: app.canvas.key,
                space: app.canvas.space.clone(),
                source,
                list,
                window: app.canvas.window,
                cache: std::mem::take(&mut app.canvas.render_cache),
            });
        }
        if let Some(at) = app.canvas.scenes.iter().position(|s| s.key.0 == st.uid && s.space == st.space)
            && let Some(scene) = app.canvas.scenes.remove(at)
        {
            app.canvas.key = scene.key;
            app.canvas.source = Some(scene.source);
            app.canvas.list = Some(scene.list);
            app.canvas.window = scene.window;
            app.canvas.render_cache = scene.cache;
            app.canvas.rebuilt_parts = 0;
            app.canvas.reused_parts = app.canvas.list.as_ref().map_or(0, |l| l.parts.len());
            app.canvas.build_ms = 0.0;
        }
        app.canvas.space = st.space.clone();
        app.canvas.key.0 = st.uid;
        app.canvas.mesh_key = None;
        app.canvas.hover_at = None;
        app.canvas.hover = None;
        app.canvas.prim_index = PrimIndex::default();
        app.canvas.list_gen = app.canvas.list_gen.wrapping_add(1);
        // Retain a few recent tabs, with one total geometry budget rather than one per tab.
        let budget = if app.tablet_mode { (app.tablet_prefs.cache_mib as usize) << 20 } else { 64 << 20 };
        while app.canvas.scenes.len() > 16 || app.canvas.scenes.iter().map(Scene::bytes).sum::<usize>() > budget {
            app.canvas.scenes.pop_front();
        }
        app.canvas.enforce_cache_budget();
    }
    // A background build that finished: use it unless the drawing has changed since it started
    // (or the list was dropped to force a rebuild).
    let mut force_sync = false;
    if let Some(job) = &app.canvas.job {
        match job.poll() {
            rebuild::Poll::Pending => {}
            rebuild::Poll::Done(built) => {
                let (job_key, window) = (job.key, job.window);
                app.canvas.job = None;
                if same_content(&job_key, &key) {
                    app.canvas.install(job_key, window, *built);
                    app.canvas.enforce_cache_budget();
                }
            }
            rebuild::Poll::Lost => {
                log::warn!("canvas: a background rebuild failed; rebuilding on the UI thread");
                app.canvas.job = None;
                app.canvas.list = None;
                force_sync = true;
            }
        }
    }
    let visible = views.iter().fold(Bounds2::EMPTY, |acc, v| acc.union(&v.0));
    let inside = app.canvas.window.is_none_or(|w| visible.is_empty() || w.contains_box(&visible));
    if app.canvas.list.is_some() && app.canvas.key == key && inside {
        return;
    }
    // Only the view moved: keep drawing the current list and build the new one in the background.
    let view_only = app.canvas.list.is_some() && same_content(&app.canvas.key, &key);
    if app.canvas.job.as_ref().is_some_and(|j| j.serves(&key, &visible)) {
        return;
    }
    // A build for another view, or for a drawing that has since changed, is no longer wanted:
    // dropping it cancels it.
    app.canvas.job = None;
    let t0 = crate::now_ms();
    let opts = cadcraft_render::Options {
        tolerance: 2f64.powi(curve_band) * 0.5,
        // Two pixels at the band's finest zoom: the list serves every zoom in the band, so its
        // level of detail must hold at the finest one.
        min_dash: 2f64.powi(lod_band) * 2.0,
        text: true,
        linetypes: true,
        fill: true,
        lineweights: lwdisplay,
        view_height: st.paper_view().height,
        plot_style_table: None,
        view: if inside && app.canvas.list.is_some() { app.canvas.window } else { build_window(views) },
        transparency: app.session.settings.transparency_display,
        skip_viewport: split,
        cancel: None,
    };
    if !force_sync && (view_only || (app.tablet_mode && app.canvas.render_cache.changed_work(&st.doc, &st.space, &opts) >= 4096)) {
        let t = Tokens::get();
        let mesh = app.canvas.gpu.is_some().then(|| rebuild::MeshRequest {
            view_center: xf.center,
            view_height: f64::from(xf.rect.height()) / xf.scale.max(1e-300),
            model_bg: Rgb(t.canvas.r(), t.canvas.g(), t.canvas.b()),
            paper_bg: Rgb(t.paper.r(), t.paper.g(), t.paper.b()),
            lwdisplay,
            device: app.canvas.gpu_device.clone(),
            queue: app.canvas.gpu_queue.clone(),
            parts: app.canvas.part_meshes.clone(),
            blocks: app.canvas.block_meshes.clone(),
            compact: app.tablet_mode,
        });
        let window = opts.view;
        let req = rebuild::Request { doc: st.doc.clone(), space: st.space.clone(), opts: opts.clone(), mesh, cache: app.canvas.render_cache.clone() };
        if let Some(job) = rebuild::spawn(req, key, window, ctx) {
            app.canvas.job = Some(job);
            return;
        }
    }
    let space = st.space.clone();
    if let Some(limit) = app.canvas.cache_limit {
        app.canvas.render_cache.set_budget(limit / 2);
    }
    let built = app.canvas.render_cache.build_scene(&st.doc, &space, &opts);
    app.canvas.rebuilt_parts = built.rebuilt;
    app.canvas.reused_parts = built.reused;
    app.canvas.list = Some(built.scene);
    app.canvas.source = Some(Arc::new((*st.doc).clone()));
    app.canvas.key = key;
    app.canvas.window = opts.view;
    app.canvas.list_gen = app.canvas.list_gen.wrapping_add(1);
    app.canvas.build_ms = crate::now_ms() - t0;
    app.canvas.enforce_cache_budget();
}

/// The display list of what a running command shows in place of the drawing
/// ([`cadcraft_engine::Session::display_only`]: DVIEW's preview set), rebuilt when the drawing,
/// the set or the 2x zoom band changes.
#[derive(Default)]
pub(super) struct OnlyList {
    key: Option<u64>,
    pub(super) list: DisplayList,
}

impl OnlyList {
    /// `outline`: a clipped viewport's outline (model units) the preview is clipped to.
    pub(super) fn update(&mut self, st: &cadcraft_engine::DocState, only: &cadcraft_engine::DisplayOnly, scale: f64, outline: Option<&[Vec2]>) {
        let band = (1.0 / scale.max(1e-300)).log2().floor() as i32;
        let key = {
            use std::hash::{Hash, Hasher};
            let mut h = std::collections::hash_map::DefaultHasher::new();
            (st.uid, st.revision, std::sync::Arc::as_ptr(&st.doc) as usize, band, &only.handles, format!("{:?}", only.extra), font_generation())
                .hash(&mut h);
            outline.into_iter().flatten().for_each(|q| (q.x.to_bits(), q.y.to_bits()).hash(&mut h));
            h.finish()
        };
        if self.key != Some(key) {
            let ents = only.handles.iter().filter_map(|h| st.doc.entity(*h)).map(|e| e.as_ref()).chain(only.extra.iter());
            let list = rebuilt_preview(&st.doc, ents, 2f64.powi(-band));
            self.list = match outline.and_then(cadcraft_render::clip::PolyClip::new) {
                Some(c) => cadcraft_render::clip_list(&list, &c),
                None => list,
            };
            self.key = Some(key);
        }
    }
}

/// The area a display list is built for: each view with half its larger side of margin all
/// round (panning by up to that much doesn't rebuild), joined. `None` (everything) when a view
/// isn't usable.
fn build_window(views: &[(Bounds2, f64)]) -> Option<Bounds2> {
    let mut w = Bounds2::EMPTY;
    for (v, _) in views {
        let side = v.width().max(v.height());
        if v.is_empty() || !side.is_finite() {
            return None;
        }
        w = w.union(&v.expand(side * 0.5));
    }
    (!w.is_empty()).then_some(w)
}
