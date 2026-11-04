package io.github.pedroguille.folio;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.Arrays;

/** Host-side checks that run against the production byte-copy/name code. */
public final class StorageTest {
    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
    public static void main(String[] args) throws Exception {
        check(Storage.safeName("../../report.docx").equals("report.docx"), "Unix filename confinement");
        check(Storage.safeName("C:\\private\\report.pdf").equals("report.pdf"), "Windows filename confinement");
        check(Storage.safeName("\u0000\n").equals("Document"), "Control-only filename fallback");
        check(Storage.safeName("..").equals("Document"), "Parent path rejected");
        StringBuilder unicode = new StringBuilder();
        for (int i = 0; i < 220; i++) unicode.append("\ud83d\udcc4");
        String safe = Storage.safeName(unicode + ".docx");
        check(safe.codePointCount(0,safe.length()) == 180 && !Character.isLowSurrogate(safe.charAt(0)), "Unicode truncation stays at code point boundary");
        check(Storage.mime("FILE.PPTX").equals("application/vnd.openxmlformats-officedocument.presentationml.presentation"), "PPTX MIME");
        byte[] source = new byte[170003];
        for (int i = 0; i < source.length; i++) source[i] = (byte)(i * 73);
        ByteArrayOutputStream copied = new ByteArrayOutputStream();
        check(Storage.copy(new ByteArrayInputStream(source),copied,source.length) == source.length, "Exact-limit byte count");
        check(Arrays.equals(source,copied.toByteArray()), "Binary copy preserves every byte");
        boolean failed = false;
        try { Storage.copy(new ByteArrayInputStream(source),new ByteArrayOutputStream(),source.length - 1); }
        catch (IOException expected) { failed = true; }
        check(failed, "Oversized input is rejected");
        System.out.println("Storage tests passed: bounded binary copy, MIME, confinement, Unicode filenames.");
    }
}
