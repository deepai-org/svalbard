import sys, numpy as np, glob
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q'); from var import S
def kmu(prefix):
    a = np.array(S.read_table(prefix + '_a.txt')); b = np.array(S.read_table(prefix + '_b.txt'))
    f = a[:, 0]; z11 = a[:, 1] + 1j * a[:, 2]; z21 = a[:, 4] + 1j * a[:, 5]; z12 = b[:, 1] + 1j * b[:, 2]; z22 = b[:, 4] + 1j * b[:, 5]
    z0 = 100.; den = (z11 + z0) * (z22 + z0) - z12 * z21
    s11 = ((z11 - z0) * (z22 + z0) - z12 * z21) / den; s22 = ((z11 + z0) * (z22 - z0) - z12 * z21) / den
    s12 = 2 * z12 * z0 / den; s21 = 2 * z21 * z0 / den; d = s11 * s22 - s12 * s21
    k = (1 - abs(s11) ** 2 - abs(s22) ** 2 + abs(d) ** 2) / (2 * abs(s12 * s21) + 1e-30)
    mu = (1 - abs(s11) ** 2) / (abs(s22 - d * np.conj(s11)) + abs(s12 * s21) + 1e-30)
    return f, k, mu, z11, z22, s12, s21
if __name__ == '__main__':
    f, k, mu, z11, z22, s12, s21 = kmu(sys.argv[1])
    bad = (k < 1) | (mu < 1)
    print('K<1 or mu<1 at GHz:', ' '.join('%.2f' % (x / 1e9) for x in f[bad]) or 'none')
    for x in (0.1, 0.5, 1, 1.5, 2, 2.44, 3, 4, 6, 8, 10, 13, 16, 20, 30):
        i = np.argmin(abs(f - x * 1e9)); print('%.2f GHz K %.2f mu %.5f Re z11 %.2f Re z22 %.2f |s21| %.1f dB |s12| %.1f dB' % (f[i] / 1e9, k[i], mu[i], z11[i].real, z22[i].real, 20 * np.log10(abs(s21[i])), 20 * np.log10(abs(s12[i]))))
