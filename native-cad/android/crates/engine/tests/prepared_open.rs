//! Android's background import participates in upstream's document-binding epoch.
use cadcraft_engine::doc::Drawing;
use cadcraft_engine::geom::Vec2;
use cadcraft_engine::{DocState, Input, Session};

#[test]
fn prepared_open_cancels_in_the_old_drawing_and_changes_the_document_epoch() {
    let mut session = Session::new();
    let old = session.active;
    session.start("line").unwrap();
    session.input(Input::Point(Vec2::ZERO)).unwrap();
    session.input(Input::Point(Vec2::new(10.0, 0.0))).unwrap();
    assert!(session.running.is_some());
    let epoch = session.doc_epoch;
    let prepared = DocState::new(Drawing::new_metric(), "Imported", None);
    let uid = prepared.uid;

    let active = session.open_prepared(prepared);

    assert_ne!(active, old);
    assert_eq!(session.state().unwrap().uid, uid);
    assert_eq!(session.doc_epoch, epoch.wrapping_add(1));
    assert!(session.running.is_none());
    assert!(session.doc().unwrap().model.is_empty());
    assert_eq!(session.docs[old].doc.model.len(), 1, "cancel completes the old drawing's line, without changing the imported document");
    assert_eq!(session.docs[old].undo.len(), 1, "the finished command's undo belongs to its original drawing");
}
