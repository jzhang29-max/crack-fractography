## References

Implementations of the five classical arms are those in scikit-image [10]; each was run
through this paper's own scoring code, not its authors'.

[1] Otsu, N. (1979). A threshold selection method from gray-level histograms.
*IEEE Transactions on Systems, Man, and Cybernetics* 9(1), 62–66.

[2] Sauvola, J. and Pietikäinen, M. (2000). Adaptive document image binarization.
*Pattern Recognition* 33(2), 225–236.

[3] Frangi, A.F., Niessen, W.J., Vincken, K.L. and Viergever, M.A. (1998). Multiscale
vessel enhancement filtering. *MICCAI 1998*, LNCS 1496, 130–137.

[4] Sato, Y., Nakajima, S., Shiraga, N., Atsumi, H., Yoshida, S., Koller, T., Gerig, G.
and Kikinis, R. (1998). Three-dimensional multi-scale line filter for segmentation and
visualization of curvilinear structures in medical images. *Medical Image Analysis* 2(2),
143–168.

[5] Meijering, E., Jacob, M., Sarria, J.-C.F., Steiner, P., Hirling, H. and Unser, M.
(2004). Design and validation of a tool for neurite tracing and analysis in fluorescence
microscopy images. *Cytometry Part A* 58(2), 167–176.

[6] Olofsson, P., Foody, G.M., Herold, M., Stehman, S.V., Woodcock, C.E. and Wulder, M.A.
(2014). Good practices for estimating area and assessing accuracy of land change.
*Remote Sensing of Environment* 148, 42–57. doi:10.1016/j.rse.2014.02.015. **The closest
prior art to Section 3.3.** Reporting the error matrix in units of area proportion, and
correcting a map-derived area for classifier bias, is standard practice in land-cover
accuracy assessment and has been for a decade. What Section 3.3 adds is not the idea but
the application to a micrograph area fraction, and a full budget rather than a single
bias-adjusted point estimate.

[7] Durmaz, A.R., Müller, M., Lei, B., Thomas, A., Britz, D., Holm, E.A., Eberl, C.,
Mücklich, F. and Gumbsch, P. (2021). A deep learning approach for complex microstructure
inference. *Nature Communications* 12, 6272. Precedent in this modality for reporting the
downstream morphological quantity beside the segmentation score, and for the observation
that phase-boundary localisation limits per-object morphology.

[8] ASTM E562-19. *Standard Test Method for Determining Volume Fraction by Systematic
Manual Point Count.* ASTM International. The units a materials laboratory reports in, and
the accuracy target Section 6 measures against.

[9] Underwood, E.E. and Banerji, K. Quantitative fractography.
doi:10.1007/BF02698249. The roughness and profile parameters the measurement side of this
tool reports.

[10] van der Walt, S., Schönberger, J.L., Nunez-Iglesias, J., Boulogne, F., Warner, J.D.,
Yager, N., Gouillart, E. and Yu, T. (2014). scikit-image: image processing in Python.
*PeerJ* 2, e453.

[11] Salvato, D. et al. (2023). Impact of SEM acquisition parameters on the porosity
analysis of irradiated U-Mo fuel. *Nuclear Materials and Energy*.
doi:10.1016/j.nme.2023.101494. Published precedent that a segmentation-derived extent
metric moves with acquisition settings, which is the effect Section 5 reports for detection
mode.

[12] Dahari, A. et al. (2025). Prediction of microstructural representativity from a single
image. *Advanced Science*. doi:10.1002/advs.202414149, arXiv:2410.19568. Bounds the
within-image representativity of a phase fraction analytically; it does not estimate
between-patch variance over a specimen surface, which is the quantity Section 7 says this
corpus cannot supply.

[13] The Inconel 718 crack class used throughout Section 3 is from a public cross-material
microstructure collection, Zenodo record 23045328, CC BY 4.0.
doi:10.5281/zenodo.23045328.

**This list is incomplete.** It covers the arms this paper runs and the prior art it has
checked itself against. It does not yet contain a survey of learned crack segmentation, and
the sentence in Section 3.4 about the published learned state of the art is uncited and
should either be sourced or deleted before submission.
