/*
 * Abflussrechnung auf einem Höhenraster: Senken füllen (Priority-Flood), Abflussrichtung (D8), Einzugsgebiet je Zelle.
 *
 * Zweck:    Rechenkern für tools/build_abfluss.py. Reines C, weil Priority-Flood über rund 150 Millionen Zellen in Python nicht in
 *           brauchbarer Zeit läuft (kein numba auf dem Mac, keine GIS-Pakete im Projekt).
 * Verfahren: Barnes, Lehman, Mulla (2014) "Priority-flood": Randzellen und Nachbarn von Lücken (NaN) kommen mit ihrer Höhe in eine
 *           Warteschlange (niedrigste zuerst, bei Gleichstand die zuerst eingetragene = FIFO, das gibt auf Ebenen brauchbare Wege).
 *           Wird eine Zelle gezogen, fließen ihre noch unbesuchten Nachbarn zu ihr; deren Höhe ist mindestens die der Zelle (Füllung).
 *           Die Zugreihenfolge ist damit eine Ordnung vom Auslauf ins Gelände. Rückwärts durchlaufen summiert sie die Fläche stromab.
 * Eingabe:  <dem.f32>  W*H Float32, zeilenweise von Nord nach Süd, NaN = keine Daten
 *           <zeilenflaeche.f32>  H Float32: Fläche einer Zelle in m² je Zeile (Web-Mercator-Pixel schrumpft mit cos(Breite))
 * Ausgabe:  <aus>.dir (uint8: 0..7 = Nachbar, 255 = Auslauf/keine Daten), <aus>.acc (Float32 m²: Fläche oberhalb inklusive der Zelle),
 *           <aus>.depth (Float32 m: Füllhöhe minus Gelände, > 0 in Senken)
 * Aufruf:   cc -O3 -o abfluss_kern tools/abfluss_kern.c -lm
 *           ./abfluss_kern dem.f32 zeilenflaeche.f32 W H aus
 * Grenzen:  Das Modell kennt weder Durchlässe noch Brücken noch Gräben unter Straßen, nur das Gelände. Am Rand des Rasters fehlt der
 *           Zufluss von außen.
 * Exit:     0 = fertig, 1 = Fehler
 */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { uint64_t key; uint32_t idx; } Item;
static Item *heap; static size_t hn, hcap;

static uint32_t fkey(float f) { uint32_t u; memcpy(&u, &f, 4); return (u & 0x80000000u) ? ~u : (u | 0x80000000u); }   /* ordnungstreu */
static void push(uint64_t key, uint32_t idx) {
    if (hn == hcap) { hcap = hcap ? hcap * 2 : 1 << 20; heap = realloc(heap, hcap * sizeof(Item)); if (!heap) { fputs("kein Speicher (Heap)\n", stderr); exit(1); } }
    size_t i = hn++;
    while (i > 0) { size_t p = (i - 1) / 2; if (heap[p].key <= key) break; heap[i] = heap[p]; i = p; }
    heap[i].key = key; heap[i].idx = idx;
}
static Item pop(void) {
    Item top = heap[0], last = heap[--hn];
    size_t i = 0;
    for (;;) {
        size_t c = 2 * i + 1;
        if (c >= hn) break;
        if (c + 1 < hn && heap[c + 1].key < heap[c].key) c++;
        if (heap[c].key >= last.key) break;
        heap[i] = heap[c]; i = c;
    }
    if (hn) heap[i] = last;
    return top;
}

static const int DX[8] = {1, 1, 0, -1, -1, -1, 0, 1}, DY[8] = {0, 1, 1, 1, 0, -1, -1, -1};

int main(int argc, char **argv) {
    if (argc != 6) { fprintf(stderr, "Aufruf: %s dem.f32 zeilenflaeche.f32 W H aus\n", argv[0]); return 1; }
    long W = atol(argv[3]), H = atol(argv[4]);
    size_t N = (size_t)W * H;
    if (W < 3 || H < 3 || N >= 0xFFFFFFFFu) { fputs("Rastergröße nicht zulässig\n", stderr); return 1; }
    float *z = malloc(N * 4), *rowa = malloc(H * 4);
    FILE *f = fopen(argv[1], "rb");
    if (!z || !rowa || !f || fread(z, 4, N, f) != N) { fputs("DEM nicht lesbar\n", stderr); return 1; }
    fclose(f);
    f = fopen(argv[2], "rb");
    if (!f || fread(rowa, 4, H, f) != (size_t)H) { fputs("Zeilenflächen nicht lesbar\n", stderr); return 1; }
    fclose(f);
    uint8_t *dir = malloc(N); memset(dir, 255, N);
    uint8_t *seen = calloc(N, 1);
    uint32_t *order = malloc(N * 4); size_t on = 0;
    float *fill = malloc(N * 4);
    if (!dir || !seen || !order || !fill) { fputs("kein Speicher\n", stderr); return 1; }
    uint64_t seq = 0;
    /* Start: Rand und Nachbarn von Lücken */
    for (long y = 0; y < H; y++) for (long x = 0; x < W; x++) {
        size_t i = (size_t)y * W + x;
        if (isnan(z[i])) { seen[i] = 1; continue; }
        int rand = (x == 0 || y == 0 || x == W - 1 || y == H - 1);
        if (!rand) for (int k = 0; k < 8 && !rand; k++) if (isnan(z[(size_t)(y + DY[k]) * W + x + DX[k]])) rand = 1;
        if (rand) { seen[i] = 1; fill[i] = z[i]; push(((uint64_t)fkey(z[i]) << 32) | (seq++ & 0xFFFFFFFFu), (uint32_t)i); }
    }
    while (hn) {
        Item it = pop();
        size_t i = it.idx; order[on++] = (uint32_t)i;
        long y = (long)(i / W), x = (long)(i % W);
        for (int k = 0; k < 8; k++) {
            long nx = x + DX[k], ny = y + DY[k];
            if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
            size_t j = (size_t)ny * W + nx;
            if (seen[j]) continue;
            seen[j] = 1;
            dir[j] = (uint8_t)((k + 4) & 7);                      /* j fließt zurück zu i */
            fill[j] = z[j] > fill[i] ? z[j] : fill[i];
            push(((uint64_t)fkey(fill[j]) << 32) | (seq++ & 0xFFFFFFFFu), (uint32_t)j);
        }
    }
    free(heap); free(seen);
    float *acc = malloc(N * 4);
    if (!acc) { fputs("kein Speicher (acc)\n", stderr); return 1; }
    for (size_t i = 0; i < N; i++) acc[i] = isnan(z[i]) ? 0.f : rowa[i / W];
    for (size_t q = on; q-- > 0;) {                            /* vom Gelände zum Auslauf */
        size_t i = order[q];
        if (dir[i] == 255) continue;
        long y = (long)(i / W), x = (long)(i % W);
        acc[(size_t)(y + DY[dir[i]]) * W + x + DX[dir[i]]] += acc[i];
    }
    for (size_t i = 0; i < N; i++) fill[i] = isnan(z[i]) ? 0.f : fill[i] - z[i];
    char name[4096];
    const char *ext[3] = {"dir", "acc", "depth"};
    void *buf[3] = {dir, acc, fill};
    size_t sz[3] = {1, 4, 4};
    for (int k = 0; k < 3; k++) {
        snprintf(name, sizeof name, "%s.%s", argv[5], ext[k]);
        f = fopen(name, "wb");
        if (!f || fwrite(buf[k], sz[k], N, f) != N) { fprintf(stderr, "%s nicht schreibbar\n", name); return 1; }
        fclose(f);
    }
    fprintf(stderr, "fertig: %zu Zellen, %zu bearbeitet\n", N, on);
    return 0;
}
