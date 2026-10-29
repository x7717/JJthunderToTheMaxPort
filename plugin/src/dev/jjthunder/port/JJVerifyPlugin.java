package dev.jjthunder.port;

import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.NamespacedKey;
import org.bukkit.Registry;
import org.bukkit.World;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * JJVerify - verification plugin for the JJThunder To The Max 26.3 port.
 *
 * Compares the LIVE server state (registries, world bounds, biomes at probed points)
 * against a manifest bundled in the plugin jar (verify-manifest.json), which is
 * generated from the ported datapack itself. /jjverify prints a PASS/FAIL report
 * and writes jjverify-report.json into the plugin data folder.
 */
public class JJVerifyPlugin extends JavaPlugin {

    private Map<String, Object> manifest;

    @Override
    public void onEnable() {
        try (InputStream in = getResource("verify-manifest.json")) {
            String json = new String(in.readAllBytes(), StandardCharsets.UTF_8);
            manifest = simpleJson(json);
        } catch (Exception e) {
            getLogger().severe("verify-manifest.json missing/broken: " + e);
        }
        getCommand("jjverify").setExecutor(this);
        getLogger().info("JJVerify loaded. Run /jjverify to verify the ported worldgen.");
    }

    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {
        // run synchronously next tick(s) - registry access is main-thread only
        Bukkit.getScheduler().runTask(this, this::verifyAndReport);
        return true;
    }

    private void verifyAndReport() {
        Report r = verify();
        for (String line : r.consoleLines) {
            getLogger().info(line.replace("§a", "").replace("§c", "").replace("§7", ""));
        }
        getLogger().info("JJVerify finished: " + r.summary);
    }

    // ------------------------------------------------------------------ verify

    @SuppressWarnings({"unchecked", "rawtypes"})
    private Report verify() {
        Report rep = new Report();

        World w = Bukkit.getWorlds().get(0);

        // 1. world bounds = the pack's tall dimension (min_y -64, height 2096)
        check(rep, "world.minHeight", String.valueOf(w.getMinHeight()), str(manifest.get("expected_min_y")));
        check(rep, "world.maxHeight", String.valueOf(w.getMaxHeight()), str(manifest.get("expected_max_height")));
        check(rep, "world.seaLevel", String.valueOf(w.getSeaLevel()), str(manifest.get("expected_sea_level")));

        // 2. biome registry contents
        Set<String> biomes = new HashSet<>();
        try {
            Registry<org.bukkit.block.Biome> reg = Bukkit.getRegistry(org.bukkit.block.Biome.class);
            for (org.bukkit.block.Biome b : reg) {
                biomes.add(reg.getKey(b).toString());
            }
        } catch (Throwable t) {
            rep.consoleLines.add("[JJVerify] biome registry unavailable: " + t);
        }
        rep.consoleLines.add("[JJVerify] biome registry size: " + biomes.size());
        List<String> mustExist = (List<String>) manifest.get("biomes_must_exist");
        for (String key : mustExist) {
            check(rep, "biome." + key, biomes.contains(key) ? "present" : "MISSING", "present");
        }

        // 3. live structure locates (the pack overrides mineshaft spacing; ancient_city etc.)
        Location origin = new Location(w, 0, 200, 0);
        for (Map<String, Object> sp : (List<Map<String, Object>>) manifest.get("structure_probes")) {
            String typeName = (String) sp.get("type");
            int maxBlocks = num(sp.get("max_blocks"));
            try {
                org.bukkit.generator.structure.StructureType type =
                        (org.bukkit.generator.structure.StructureType)
                                org.bukkit.generator.structure.StructureType.class.getField(typeName).get(null);
                org.bukkit.util.StructureSearchResult result =
                        w.locateNearestStructure(origin, type, maxBlocks + 1000, true);
                Location found = result == null ? null : result.getLocation();
                int dist = found == null ? -1
                        : (int) Math.max(Math.abs(found.getX() - origin.getX()), Math.abs(found.getZ() - origin.getZ()));
                rep.checks++;
                boolean ok = found != null && dist <= maxBlocks;
                if (!ok) rep.failures++;
                String actualS = found == null ? "NOT FOUND" : dist + " blocks (limit " + maxBlocks + ")";
                rep.consoleLines.add((ok ? "§a[OK] " : "§c[FAIL] ") + "structure_locate." + typeName + " = " + actualS);
                rep.results.put("structure_locate." + typeName,
                        Map.of("actual", actualS, "expected", "within " + maxBlocks, "pass", ok));
                getLogger().info((ok ? "[OK] " : "[FAIL] ") + "structure_locate." + typeName + " = " + actualS);
            } catch (Throwable t) {
                rep.checks++; rep.failures++;
                String msg = "error: " + t;
                rep.consoleLines.add("§c[FAIL] structure_locate." + typeName + " = " + msg);
                rep.results.put("structure_locate." + typeName,
                        Map.of("actual", msg, "expected", "within " + maxBlocks, "pass", false));
            }
        }

        // 4. live biome probes at manifest points (biome provider round-trip)
        for (Map<String, Object> probe : (List<Map<String, Object>>) manifest.get("biome_probes")) {
            int x = num(probe.get("x")), y = num(probe.get("y")), z = num(probe.get("z"));
            String expected = (String) probe.get("biome");
            String actual;
            try {
                actual = w.getBiome(new Location(w, x, y, z)).getKey().toString();
            } catch (Throwable t) {
                actual = "error: " + t;
            }
            check(rep, "probe[" + x + "," + y + "," + z + "]", actual, expected);
        }

        // 5. summary + report file
        rep.summary = rep.failures == 0
                ? "PASS - " + rep.checks + " checks OK"
                : "FAIL - " + rep.failures + " of " + rep.checks + " checks failed";
        rep.consoleLines.add(0, (rep.failures == 0 ? "§a" : "§c") + "[JJVerify] " + rep.summary);
        rep.consoleLines.add("§7[JJVerify] details: plugins/JJVerify/jjverify-report.json");
        saveReport(rep);
        return rep;
    }

    private void check(Report rep, String key, String actual, String expected) {
        rep.checks++;
        boolean ok = actual.equals(expected);
        if (!ok) rep.failures++;
        rep.consoleLines.add((ok ? "§a[OK] " : "§c[FAIL] ") + key + " = " + actual
                + (ok ? "" : " (expected " + expected + ")"));
        rep.results.put(key, Map.of("actual", actual, "expected", expected, "pass", ok));
        getLogger().info((ok ? "[OK] " : "[FAIL] ") + key + " = " + actual
                + (ok ? "" : " (expected " + expected + ")"));
    }

    private void saveReport(Report rep) {
        try {
            Path dir = getDataFolder().toPath();
            Files.createDirectories(dir);
            StringBuilder sb = new StringBuilder("{\n  \"summary\": \"").append(rep.summary.replace("\"", "'"))
                    .append("\",\n  \"results\": {\n");
            List<String> parts = new ArrayList<>();
            for (Map.Entry<String, Map<String, Object>> e : rep.results.entrySet()) {
                Map<String, Object> v = e.getValue();
                parts.add(String.format("    \"%s\": {\"actual\": \"%s\", \"expected\": \"%s\", \"pass\": %s}",
                        e.getKey(), v.get("actual"), v.get("expected"), v.get("pass")));
            }
            sb.append(String.join(",\n", parts)).append("\n  }\n}\n");
            Files.write(dir.resolve("jjverify-report.json"), sb.toString().getBytes(StandardCharsets.UTF_8));
        } catch (Exception e) {
            getLogger().warning("could not save report: " + e);
        }
    }

    private static String str(Object o) { return String.valueOf(o); }
    private static int num(Object o) { return ((Number) o).intValue(); }

    private static class Report {
        int checks = 0, failures = 0;
        String summary = "";
        final List<String> consoleLines = new ArrayList<>();
        final Map<String, Map<String, Object>> results = new LinkedHashMap<>();
    }

    // ------------------------------------------------------- tiny JSON parser
    // (keeps the plugin dependency-free; the manifest is machine-generated)

    private static Map<String, Object> simpleJson(String s) {
        return (Map<String, Object>) new P(s).parse();
    }

    private static final class P {
        final String s; int i = 0;
        P(String s) { this.s = s; }
        Object parse() {
            skip(); char c = s.charAt(i);
            if (c == '{') { Map<String, Object> m = new LinkedHashMap<>(); i++;
                while (true) { skip(); if (s.charAt(i) == '}') { i++; return m; }
                    String k = str(); skip(); expect(':'); m.put(k, parse()); skip();
                    if (s.charAt(i) == ',') { i++; } else { expect('}'); return m; } } }
            if (c == '[') { List<Object> l = new ArrayList<>(); i++;
                while (true) { skip(); if (s.charAt(i) == ']') { i++; return l; }
                    l.add(parse()); skip();
                    if (s.charAt(i) == ',') { i++; } else { expect(']'); return l; } } }
            if (c == '"') return str();
            int st = i;
            while (i < s.length() && "-+.eE0123456789truefalsn".indexOf(s.charAt(i)) >= 0) i++;
            String t = s.substring(st, i);
            if (t.equals("true")) return Boolean.TRUE;
            if (t.equals("false")) return Boolean.FALSE;
            if (t.contains(".") || t.contains("e")) return Double.parseDouble(t);
            return t.matches("-?\\d+") ? Long.parseLong(t) : t;
        }
        String str() { StringBuilder b = new StringBuilder(); expect('"');
            while (s.charAt(i) != '"') { if (s.charAt(i) == '\\') i++; b.append(s.charAt(i)); i++; } i++; return b.toString(); }
        void skip() { while (i < s.length() && Character.isWhitespace(s.charAt(i))) i++; }
        void expect(char c) { if (s.charAt(i) != c) throw new IllegalStateException("expected " + c + " at " + i); i++; }
    }
}
