package com.stemplay.library;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class LibraryGenerator {

    private static final Pattern LESSON = Pattern.compile("(?:Aula|Lesson|Class)\\s*0*(\\d+)", Pattern.CASE_INSENSITIVE);
    private static final Pattern UNIT = Pattern.compile("(?:Unit|Unidade|Und)\\s*0*(\\d+)", Pattern.CASE_INSENSITIVE);
    private static final Pattern UNIT_FALLBACK = Pattern.compile("[_-]U0*(\\d+)[_-]", Pattern.CASE_INSENSITIVE);
    private static final Pattern MODULE = Pattern.compile("(?:Modulo|_M|[-_]M)0*(\\d+)", Pattern.CASE_INSENSITIVE);
    private static final Pattern CHECKPOINT = Pattern.compile("Checkpoint\\s*0*(\\d+)", Pattern.CASE_INSENSITIVE);
    private static final Pattern CAPITULO = Pattern.compile("Capitulo\\s*0*(\\d+)", Pattern.CASE_INSENSITIVE);
    private static final Pattern KEYWORD_PATTERNS[] = {
            Pattern.compile("Grammar\\s*Reference", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Checkpoint\\s*Key", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Answer\\s*Key", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Audio\\s*Scripts?", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Extra\\s*Resources?", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Workbook\\s*Answer\\s*Key", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Consolidation.*Key", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Workbook(?!Answer)", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Unit\\s*00", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Teacher\\s*Book", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Student\\s*Book", Pattern.CASE_INSENSITIVE),
            Pattern.compile("Song\\s*Book", Pattern.CASE_INSENSITIVE),
    };
    private static final String[] KEYWORD_NAMES = {
            "Grammar Reference", "Checkpoint Key", "Answer Key", "Audio Script",
            "Extra Resources", "Workbook Answer Key", "Consolidation Key", "Workbook",
            "Unit 00", "Teacher Book", "Student Book", "Song Book"
    };
    private static final Pattern COURSE_CLEAN = Pattern.compile("[-_](TEACHER|STUDENT|WORKBOOK)$", Pattern.CASE_INSENSITIVE);
    private static final String[] SEGMENTS_SKIP = {
            "ENGLISH", "TEEN1", "TEEN2", "TEEN3", "JUNIOR", "PLENO",
            "STUDENT", "TEACHER", "BOOK", "WORKBOOK", "COM", "DE",
            "AO", "LV1", "LV2", "I", "II", "III", "INICIANTE", "CB", "HAPPY", "KIDS", "SONG"
    };

    public static String generateJson(List<String> pdfUrls) {
        List<Map<String, Object>> pdfs = new ArrayList<>();
        for (String url : pdfUrls) {
            Map<String, Object> info = parsePdfInfo(url);
            if (info != null) pdfs.add(info);
        }

        List<Map<String, Object>> deduped = deduplicate(pdfs);
        Map<String, List<Map<String, Object>>> coursesMap = new LinkedHashMap<>();
        for (Map<String, Object> pdf : deduped) {
            String course = (String) pdf.get("course");
            coursesMap.computeIfAbsent(course, k -> new ArrayList<>()).add(pdf);
        }

        List<Map<String, Object>> courses = new ArrayList<>();
        for (Map.Entry<String, List<Map<String, Object>>> entry : coursesMap.entrySet()) {
            List<Map<String, Object>> items = new ArrayList<>(entry.getValue());
            Collections.sort(items, (a, b) -> compareSortKeys(
                    (int[]) a.get("sort_key"), (int[]) b.get("sort_key")));
            Map<String, Object> course = new HashMap<>();
            course.put("name", entry.getKey());
            course.put("items", items);
            courses.add(course);
        }

        courses.sort(Comparator.comparing(c -> (String) c.get("name")));
        return coursesToJson(courses);
    }

    private static int compareSortKeys(int[] x, int[] y) {
        for (int i = 0; i < 3; i++) {
            if (x[i] != y[i]) return Integer.compare(x[i], y[i]);
        }
        return 0;
    }

    private static List<Map<String, Object>> deduplicate(List<Map<String, Object>> pdfs) {
        List<Map<String, Object>> result = new ArrayList<>();
        java.util.Set<String> seenUrls = new java.util.HashSet<>();
        java.util.Set<String> seenContent = new java.util.HashSet<>();

        for (Map<String, Object> pdf : pdfs) {
            String url = (String) pdf.get("url");
            if (seenUrls.contains(url)) continue;
            seenUrls.add(url);

            String key = ((String) pdf.get("course")).toLowerCase() + "|" +
                    ((String) pdf.get("display_name")).toLowerCase() + "|" +
                    ((String) pdf.get("material_type")).toLowerCase() + "|" +
                    ((String) pdf.get("group_name")).toLowerCase();
            if (seenContent.contains(key)) continue;
            seenContent.add(key);

            result.add(pdf);
        }
        return result;
    }

    public static Map<String, Object> parsePdfInfo(String url) {
        try {
            String[] urlParts = url.split("/");
            String filenameWithPdf = urlParts[urlParts.length - 1];
            String filename = filenameWithPdf.replace(".pdf", "");
            String courseRaw = urlParts.length > 4 ? urlParts[4] : "OUTROS";
            String courseClean = COURSE_CLEAN.matcher(courseRaw).replaceAll("").trim();
            if (courseClean.isEmpty()) courseClean = courseRaw;
            String course = courseClean.replace("-", " ").replace("_", " ").trim();
            course = titleCase(course);

            String fnUp = filename.toUpperCase();
            String urlUp = url.toUpperCase();
            String[] tokens = fnUp.split("[-_\\s\\.]+");

            boolean hasWorkbook = containsToken(tokens, "WORKBOOK") || fnUp.contains("WORKBOOK");
            boolean hasStudentBook = fnUp.contains("STUDENT") && fnUp.contains("BOOK");
            boolean hasTeacher = containsToken(tokens, "TEACHER") || fnUp.endsWith("_TEACHER") || fnUp.endsWith("-TEACHER");
            boolean hasStudent = containsToken(tokens, "STUDENT");
            boolean pathIsTeacher = urlUp.contains("/TEACHER/") && !urlUp.contains("/STUDENT/");
            boolean pathIsStudent = urlUp.contains("/STUDENT/");
            boolean pathIsWorkbook = urlUp.contains("/WORKBOOK/");

            String materialType;
            if (hasWorkbook) materialType = "Workbook";
            else if (hasStudentBook) materialType = "Student";
            else if (hasStudent && hasTeacher) materialType = "Student";
            else if (hasStudent) materialType = "Student";
            else if (hasTeacher) materialType = "Teacher";
            else if (pathIsWorkbook) materialType = "Workbook";
            else if (pathIsStudent) materialType = "Student";
            else if (pathIsTeacher) materialType = "Teacher";
            else materialType = "Standard";

            Integer lessonNum = extractInt(LESSON, filename);
            Integer unitNum = extractInt(UNIT, filename);
            if (unitNum == null) unitNum = extractInt(UNIT_FALLBACK, filename);
            Integer moduleNum = extractInt(MODULE, filename);
            Integer checkpointNum = extractInt(CHECKPOINT, filename);
            Integer capituloNum = extractInt(CAPITULO, filename);

            String displayName = null;
            if (lessonNum != null) displayName = String.format("Aula %02d", lessonNum);
            else if (checkpointNum != null) displayName = String.format("Checkpoint %02d", checkpointNum);
            else if (capituloNum != null) displayName = String.format("Cap\u00edtulo %02d", capituloNum);
            else if (unitNum != null) displayName = String.format("Unidade %02d", unitNum);
            else if (moduleNum != null) displayName = "Modulo " + moduleNum;

            if (displayName == null) {
                for (int i = 0; i < KEYWORD_PATTERNS.length; i++) {
                    if (KEYWORD_PATTERNS[i].matcher(filename).find()) {
                        displayName = KEYWORD_NAMES[i];
                        break;
                    }
                }
            }

            if (displayName == null) {
                String[] segments = filename.split("[-_]");
                java.util.List<String> meaningful = new ArrayList<>();
                java.util.Set<String> skipSet = new java.util.HashSet<>();
                for (String s : SEGMENTS_SKIP) skipSet.add(s);
                for (String s : segments) {
                    String upper = s.toUpperCase();
                    if (!skipSet.contains(upper) && s.length() > 2 && !s.matches("\\d+")) {
                        meaningful.add(s);
                    }
                }
                if (!meaningful.isEmpty()) {
                    int start = Math.max(0, meaningful.size() - 2);
                    StringBuilder sb = new StringBuilder();
                    for (int i = start; i < meaningful.size(); i++) {
                        if (sb.length() > 0) sb.append(" ");
                        sb.append(titleCase(meaningful.get(i)));
                    }
                    displayName = sb.toString();
                } else {
                    displayName = filename.replace("_", " ").replace("-", " ").trim();
                    displayName = titleCase(displayName);
                }
            }

            int[] sortKey;
            String groupName;
            if (checkpointNum != null) {
                sortKey = new int[]{0, 0, checkpointNum};
                groupName = "Checkpoints";
            } else if (capituloNum != null) {
                sortKey = new int[]{unitNum != null ? unitNum : 0, capituloNum, 0};
                groupName = unitNum != null ? String.format("Unidade %02d", unitNum) : "Cap\u00edtulos";
            } else if (moduleNum != null && lessonNum != null) {
                sortKey = new int[]{moduleNum, lessonNum, 0};
                groupName = "Modulo " + moduleNum;
            } else if (moduleNum != null) {
                sortKey = new int[]{moduleNum, 0, 0};
                groupName = "Modulo " + moduleNum;
            } else if (unitNum != null) {
                sortKey = new int[]{unitNum, 0, 0};
                groupName = "Unidades";
            } else {
                sortKey = new int[]{999, 0, 0};
                groupName = "Geral";
            }

            Map<String, Object> info = new HashMap<>();
            info.put("url", url);
            info.put("course", course);
            info.put("course_raw", courseRaw);
            info.put("display_name", displayName);
            info.put("material_type", materialType);
            info.put("lesson_num", lessonNum != null ? lessonNum : 0);
            info.put("unit_num", unitNum != null ? unitNum : 0);
            info.put("module_num", moduleNum != null ? moduleNum : 0);
            info.put("checkpoint_num", checkpointNum != null ? checkpointNum : 0);
            info.put("capitulo_num", capituloNum != null ? capituloNum : 0);
            info.put("sort_key", sortKey);
            info.put("group_name", groupName);
            return info;
        } catch (Exception e) {
            return null;
        }
    }

    private static boolean containsToken(String[] tokens, String target) {
        for (String t : tokens) {
            if (t.equals(target)) return true;
        }
        return false;
    }

    private static Integer extractInt(Pattern p, String input) {
        Matcher m = p.matcher(input);
        return m.find() ? Integer.parseInt(m.group(1)) : null;
    }

    private static String titleCase(String s) {
        if (s == null || s.isEmpty()) return s;
        String[] words = s.split("\\s+");
        StringBuilder sb = new StringBuilder();
        for (String w : words) {
            if (sb.length() > 0) sb.append(" ");
            if (w.isEmpty()) continue;
            sb.append(Character.toUpperCase(w.charAt(0)));
            if (w.length() > 1) sb.append(w.substring(1).toLowerCase());
        }
        return sb.toString();
    }

    private static String coursesToJson(List<Map<String, Object>> courses) {
        StringBuilder sb = new StringBuilder();
        sb.append("[");
        for (int i = 0; i < courses.size(); i++) {
            if (i > 0) sb.append(",");
            Map<String, Object> c = courses.get(i);
            sb.append("{\"name\":").append(jsonStr((String) c.get("name")));
            sb.append(",\"items\":[");
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> items = (List<Map<String, Object>>) c.get("items");
            for (int j = 0; j < items.size(); j++) {
                if (j > 0) sb.append(",");
                Map<String, Object> item = items.get(j);
                sb.append("{");
                sb.append("\"url\":").append(jsonStr((String) item.get("url")));
                sb.append(",\"course\":").append(jsonStr((String) item.get("course")));
                sb.append(",\"display_name\":").append(jsonStr((String) item.get("display_name")));
                sb.append(",\"material_type\":").append(jsonStr((String) item.get("material_type")));
                sb.append(",\"group_name\":").append(jsonStr((String) item.get("group_name")));
                sb.append(",\"lesson_num\":").append(item.get("lesson_num"));
                sb.append(",\"unit_num\":").append(item.get("unit_num"));
                sb.append(",\"module_num\":").append(item.get("module_num"));
                sb.append(",\"checkpoint_num\":").append(item.get("checkpoint_num"));
                sb.append(",\"capitulo_num\":").append(item.get("capitulo_num"));
                sb.append("}");
            }
            sb.append("]}");
        }
        sb.append("]");
        return sb.toString();
    }

    private static String jsonStr(String s) {
        if (s == null) return "\"\"";
        return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"")
                .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t") + "\"";
    }
}
