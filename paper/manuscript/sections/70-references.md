## References

[1] Durmaz AR, Muller M, Lei B, Thomas A, Britz D, Holm EA, Eberl C, Mucklich F, Gumbsch P.
A deep learning approach for complex microstructure inference. Nature Communications.
2021;12:6272. doi:10.1038/s41467-021-26565-5.

[2] Stuckner J, Harder B, Smith TM. Microstructure segmentation with deep learning encoders
pre-trained on a large microscopy dataset. npj Computational Materials. 2022;8:200.
doi:10.1038/s41524-022-00878-5.

[3] Maier-Hein L, Reinke A, Godau P, et al. Metrics reloaded: recommendations for image
analysis validation. Nature Methods. 2024;21:195-212. doi:10.1038/s41592-023-02151-z.

[4] Reinke A, Tizabi MD, Baumgartner M, et al. Understanding metric-related pitfalls in image
analysis validation. Nature Methods. 2024;21:182-194. doi:10.1038/s41592-023-02150-0.

[5] Olofsson P, Foody GM, Herold M, Stehman SV, Woodcock CE, Wulder MA. Good practices for
estimating area and assessing accuracy of land change. Remote Sensing of Environment.
2014;148:42-57. doi:10.1016/j.rse.2014.02.015.

[6] ASTM International. ASTM E562-19e1 Standard Test Method for Determining Volume Fraction
by Systematic Manual Point Count. West Conshohocken, PA: ASTM International; 2020.
doi:10.1520/E0562-19E01.

[7] Tian J. Cross-Material Few-Shot Segmentation for Generalizable Microstructure Analysis.
Version 1. Zenodo; 2026. Dataset. doi:10.5281/zenodo.23045328.

[8] Sauvola J, Pietikainen M. Adaptive document image binarization. Pattern Recognition.
2000;33:225-236. doi:10.1016/S0031-3203(99)00055-2.

[9] Sato Y, Nakajima S, Shiraga N, et al. Three-dimensional multi-scale line filter for
segmentation and visualization of curvilinear structures in medical images. Medical Image
Analysis. 1998;2:143-168. doi:10.1016/S1361-8415(98)80009-1.

[10] Frangi AF, Niessen WJ, Vincken KL, Viergever MA. Multiscale vessel enhancement
filtering. In: Medical Image Computing and Computer-Assisted Intervention MICCAI 1998.
Lecture Notes in Computer Science. 1998;1496:130-137. doi:10.1007/BFb0056195.

[11] Meijering E, Jacob M, Sarria JCF, Steiner P, Hirling H, Unser M. Design and validation
of a tool for neurite tracing and analysis in fluorescence microscopy images. Cytometry Part
A. 2004;58A:167-176. doi:10.1002/cyto.a.20022.

[12] van der Walt S, Schonberger JL, Nunez-Iglesias J, et al. scikit-image: image processing
in Python. PeerJ. 2014;2:e453. doi:10.7717/peerj.453.

[13] Luengo J, Moreno R, Sevillano I, Charte D, Pelaez-Vegas A, Fernandez-Moreno M, Mesejo P,
Herrera F. A tutorial on the segmentation of metallographic images: Taxonomy, new MetalDAM
dataset, deep learning-based ensemble model, experimental analysis and challenges.
Information Fusion. 2022;78:232-253. doi:10.1016/j.inffus.2021.09.018.

[14] ExpertSegmentation: Segmentation for microscopy with domain-informed targets via custom
loss. Acta Materialia. 2025. doi:10.1016/j.actamat.2025.120894. *Argues that classical
methods retain an advantage because domain knowledge such as a known phase volume fraction
can be imposed explicitly, and evaluates volume-fraction alignment rather than overlap.
Reference details require confirmation against the published record.*

[15] SAMM: a general-purpose segmentation model for material micrographs based on the segment
anything model 2. 2026. doi:10.1016/j.mtcomm.2026.100126. *Adds a boundary F1 score to better
reflect fitting of grain boundaries, phase boundaries and particle edges. Reference details
require confirmation.*

[16] Context Determines Optimal Architecture in Materials Segmentation. arXiv:2602.04154.
2026. *Warns that segmentation errors propagate undetected into porosity fractions and
grain-size distributions, and that aggregate metrics can miss the failures.*

[17] Analysis of SEM digital images to quantify crack network pattern area in chromium
electrodeposits. Surface and Coatings Technology. 2015.
doi:10.1016/j.surfcoat.2015.10.052. *The closest methodological ancestor: histogram-threshold
binarisation of SEM crack networks with a Laplacian-of-Gaussian threshold choice, reporting
cracked area. Reference details require confirmation.*

[18] Improvement of qualitative analysis of scanning electron microscope images by
computational tools: binarisation, Otsu thresholding and Laplacian filters, reporting crack
length and total crack length per unit area. Journal of Microscopy. 2016. *Reference details
require confirmation.*

[19] Tegetmeyer-Kleine T, Schmitt J, Aquino A, Rahe C, Sauer DU, Li W. Data-efficient crack
quantification in lithium-ion cathodes using foundation model transfer. arXiv:2608.27162.
2026. *A different material system, but independently reports modest overlap scores on narrow
cracks, attributes them to one-to-two-pixel boundary placement, and reports area fraction,
width and tortuosity as the primary quantities.*

[20] Image-Based Fracture Surface Defect Characterization Methods for Additively Manufactured
Ti-6Al-4V Tested in Fatigue. JOM. 2024. doi:10.1007/s11837-024-06655-7. *Reports that
non-learned segmentation struggles on rough fracture surfaces because manual intensity
thresholds vary across features, which is the difficulty the background-correction stage here
addresses.*

**Note on references 14 to 18 and 20.** These were located during a literature sweep for
this revision and their bibliographic details have not all been confirmed against the
publisher records. Confirm each before submission; the substantive claims attributed to them
in Section 1 are summaries of search results, not of full texts read in the original.
