// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Fancy Butler
//
// s4tone: plays a test tone through the Traktor Kontrol S4 MK1's own sound card over libusb,
// without the Linux kernel driver. Proves the audio streaming format before it goes into S4 Bridge.
//
//   build:  cc -O2 -Wall s4tone.c -o s4tone $(pkg-config --cflags --libs libusb-1.0) -lm
//   run:    ./s4tone [seconds]          (quit S4 Bridge first; it needs the S4 to itself)
//
// Main out: 440 Hz.  Headphones: 660 Hz.  Both at -24 dBFS: turn LEVEL down before running.
// Also reports the level arriving on the rear inputs C and D, and any framing (check byte) errors.
//
// Protocol from the Linux snd-usb-caiaq driver (sound/usb/caiaq/audio.c, device.c):
//   interface 0 alt 1; EP1 bulk commands; EP2 iso IN (capture); EP6 iso OUT (playback).
//   AUDIO_PARAMS (0x09): rate code, depth code, bytes-per-packet (le16), packets per microframe.
//   Every IN packet is answered with an OUT packet of the same length (the S4 sets the clock).
//   "Mode 3" framing: per frame, per stream, per channel: 3 sample bytes (S24 big-endian), then a
//   check byte (stream << 1 | channel).

#include <libusb-1.0/libusb.h>
#include <math.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define VID 0x17cc
#define PID 0xbaff
#define EP1_OUT 0x01
#define EP1_IN 0x81
#define EP_CAPTURE 0x82
#define EP_PLAYBACK 0x06

#define CMD_GET_DEVICE_INFO 0x01
#define CMD_AUDIO_PARAMS 0x09
#define RATE_48000 1
#define DEPTH_24 2

#define N_XFERS 32
#define PACKETS 8
#define PACKET_BYTES 512
#define CHANNELS 2
#define BYTES_USB 4   /* 3 sample bytes + 1 check byte */

static volatile int running = 1;
static int n_streams = 2;
static long frames_out = 0, packets_in = 0, check_errors = 0, first_packets = 4;
static double phase[2];
static double peak_in[2][2];

static libusb_device_handle *h;
static struct libusb_transfer *in_x[N_XFERS], *out_x[N_XFERS];
static int out_busy[N_XFERS];

static void on_sigint(int s) { (void)s; running = 0; }

static void put_s24be(uint8_t *p, double v)
{
    int32_t s = (int32_t)lrint(v * 8388607.0);
    p[0] = (uint8_t)(s >> 16);
    p[1] = (uint8_t)(s >> 8);
    p[2] = (uint8_t)s;
}

static double get_s24be(const uint8_t *p)
{
    int32_t s = (int32_t)((uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8) >> 8;
    return s / 8388608.0;
}

static void fill_out(uint8_t *buf, int len)
{
    const double amp = pow(10.0, -24.0 / 20.0);
    const double freq[2] = {440.0, 660.0};      /* stream 0 = main, stream 1 = headphones */
    for (int i = 0; i + n_streams * CHANNELS * BYTES_USB <= len;) {
        for (int st = 0; st < n_streams; st++) {
            double v = st < 2 ? amp * sin(phase[st]) : 0.0;
            if (st < 2) {
                phase[st] += 2.0 * M_PI * freq[st] / 48000.0;
                if (phase[st] > 2.0 * M_PI) phase[st] -= 2.0 * M_PI;
            }
            for (int c = 0; c < CHANNELS; c++) {
                put_s24be(buf + i, v);
                i += 3;
                buf[i++] = (uint8_t)((st << 1) | c);
            }
        }
        frames_out++;
    }
}

static void read_in(const uint8_t *buf, int len)
{
    if (len % (BYTES_USB * CHANNELS))
        return;
    for (int i = 0; i < len;) {
        for (int st = 0; st < n_streams && i < len; st++)
            for (int c = 0; c < CHANNELS && i < len; c++) {
                double v = fabs(get_s24be(buf + i));
                if (st < 2 && v > peak_in[st][c]) peak_in[st][c] = v;
                i += 3;
                if (buf[i] != ((st << 1) | c) && first_packets <= 0)
                    check_errors++;
                i++;
            }
    }
    if (first_packets > 0) first_packets--;
}

static void LIBUSB_CALL out_done(struct libusb_transfer *x)
{
    out_busy[(intptr_t)x->user_data] = 0;
}

static void LIBUSB_CALL in_done(struct libusb_transfer *x)
{
    if (!running || x->status == LIBUSB_TRANSFER_CANCELLED)
        return;
    if (x->status == LIBUSB_TRANSFER_COMPLETED) {
        int slot = -1;
        for (int i = 0; i < N_XFERS; i++)
            if (!out_busy[i]) { slot = i; break; }
        int off = 0, n = 0;
        if (slot >= 0) {
            struct libusb_transfer *o = out_x[slot];
            for (int p = 0; p < x->num_iso_packets; p++) {
                struct libusb_iso_packet_descriptor *d = &x->iso_packet_desc[p];
                if (d->status != LIBUSB_TRANSFER_COMPLETED)
                    continue;
                int len = (int)d->actual_length;
                uint8_t *ib = libusb_get_iso_packet_buffer_simple(x, p);
                read_in(ib, len);
                packets_in++;
                o->iso_packet_desc[n].length = (unsigned)len;
                fill_out(o->buffer + off, len);
                off += len;
                n++;
            }
            if (n) {
                o->num_iso_packets = n;
                o->length = off;
                /* packets may differ in length: lay them out back to back */
                out_busy[slot] = 1;
                if (libusb_submit_transfer(o) < 0)
                    out_busy[slot] = 0;
            }
        }
    }
    for (int p = 0; p < PACKETS; p++)
        x->iso_packet_desc[p].length = PACKET_BYTES;
    if (running)
        libusb_submit_transfer(x);
}

static int ep1(const uint8_t *cmd, int n, uint8_t *reply, int max, uint8_t want)
{
    int done = 0;
    if (libusb_bulk_transfer(h, EP1_OUT, (uint8_t *)cmd, n, &done, 1000) < 0)
        return -1;
    for (int tries = 0; tries < 20; tries++) {
        int got = 0;
        int r = libusb_bulk_transfer(h, EP1_IN, reply, max, &got, 250);
        if (r == 0 && got > 0 && reply[0] == want)
            return got;
    }
    return -1;
}

int main(int argc, char **argv)
{
    int seconds = argc > 1 ? atoi(argv[1]) : 10;
    int detached = 0, rc = 1;
    signal(SIGINT, on_sigint);

    if (libusb_init(NULL) < 0) { fprintf(stderr, "libusb init failed\n"); return 1; }
    h = libusb_open_device_with_vid_pid(NULL, VID, PID);
    if (!h) { fprintf(stderr, "S4 not found (plugged in, switched on, permissions?)\n"); return 1; }
    if (libusb_kernel_driver_active(h, 0) == 1) {
        if (libusb_detach_kernel_driver(h, 0) == 0) detached = 1;
    }
    if (libusb_claim_interface(h, 0) < 0) { fprintf(stderr, "can't claim the S4 (is S4 Bridge running?)\n"); goto out; }
    if (libusb_set_interface_alt_setting(h, 0, 1) < 0) { fprintf(stderr, "alt setting failed\n"); goto out; }

    uint8_t rep[64];
    uint8_t info = CMD_GET_DEVICE_INFO;
    int got = ep1(&info, 1, rep, sizeof rep, CMD_GET_DEVICE_INFO);
    if (got >= 15) {
        int fw = rep[1] | rep[2] << 8;
        /* reply: cmd, fw(le16), hw_subtype, erp, analog_in, digital_in, digital_out,
           analog_audio_out, analog_audio_in, digital_audio_out, digital_audio_in, midi_out, midi_in,
           data_alignment */
        int aout = rep[8] > rep[10] ? rep[8] : rep[10];
        int ain = rep[9] > rep[11] ? rep[9] : rep[11];
        int align = rep[14];
        n_streams = (aout > ain ? aout : ain) / CHANNELS;
        printf("S4 firmware %d: audio %d out / %d in, %d streams, data alignment %d\n", fw, aout, ain,
               n_streams, align);
        if (align != 3) printf("warning: expected data alignment 3 for the S4\n");
    } else {
        printf("no device info reply; assuming 2 streams\n");
    }
    if (n_streams < 1 || n_streams > 4) n_streams = 2;

    int bpp = (48000 / 8000 + 5) * BYTES_USB * CHANNELS * n_streams;
    if (bpp > PACKET_BYTES) bpp = PACKET_BYTES;
    uint8_t params[6] = {CMD_AUDIO_PARAMS, RATE_48000, DEPTH_24, (uint8_t)(bpp & 0xff), (uint8_t)(bpp >> 8), 1};
    got = ep1(params, sizeof params, rep, sizeof rep, CMD_AUDIO_PARAMS);
    if (got < 2 || rep[1] != 1) { fprintf(stderr, "S4 refused 48 kHz / 24-bit (answer %d)\n", got >= 2 ? rep[1] : -1); goto out; }
    printf("48 kHz / 24-bit accepted (%d bytes per packet)\n", bpp);

    for (int i = 0; i < N_XFERS; i++) {
        in_x[i] = libusb_alloc_transfer(PACKETS);
        out_x[i] = libusb_alloc_transfer(PACKETS);
        uint8_t *ib = calloc(PACKETS, PACKET_BYTES), *ob = calloc(PACKETS, PACKET_BYTES);
        libusb_fill_iso_transfer(in_x[i], h, EP_CAPTURE, ib, PACKETS * PACKET_BYTES, PACKETS, in_done, NULL, 1000);
        libusb_set_iso_packet_lengths(in_x[i], PACKET_BYTES);
        libusb_fill_iso_transfer(out_x[i], h, EP_PLAYBACK, ob, PACKETS * PACKET_BYTES, PACKETS, out_done,
                                 (void *)(intptr_t)i, 1000);
    }
    for (int i = 0; i < N_XFERS; i++)
        if (libusb_submit_transfer(in_x[i]) < 0) { fprintf(stderr, "couldn't start capture stream\n"); goto out; }

    printf("Playing: 440 Hz on Main, 660 Hz on Headphones, %d s (Ctrl+C stops)\n", seconds);
    time_t t0 = time(NULL), last = t0;
    while (running && time(NULL) - t0 < seconds) {
        struct timeval tv = {0, 100000};
        libusb_handle_events_timeout(NULL, &tv);
        if (time(NULL) != last) {
            last = time(NULL);
            printf("  %2lds  packets %6ld  frames out %7ld  check errors %ld  input peaks C %.3f/%.3f  D %.3f/%.3f\n",
                   (long)(last - t0), packets_in, frames_out, check_errors,
                   peak_in[0][0], peak_in[0][1], peak_in[1][0], peak_in[1][1]);
            memset(peak_in, 0, sizeof peak_in);
            fflush(stdout);
        }
    }
    running = 0;
    for (int i = 0; i < N_XFERS; i++) { libusb_cancel_transfer(in_x[i]); libusb_cancel_transfer(out_x[i]); }
    for (int k = 0; k < 10; k++) { struct timeval tv = {0, 50000}; libusb_handle_events_timeout(NULL, &tv); }
    double rate = frames_out / (double)(time(NULL) - t0 > 0 ? time(NULL) - t0 : 1);
    printf("done: %ld packets, ~%.0f frames/s sent (expect ~48000), %ld check errors\n", packets_in, rate, check_errors);
    rc = check_errors ? 2 : 0;
out:
    libusb_release_interface(h, 0);
    if (detached) libusb_attach_kernel_driver(h, 0);
    libusb_close(h);
    libusb_exit(NULL);
    return rc;
}
