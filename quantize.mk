SRCDIR := $(patsubst %/,%,$(dir $(lastword $(MAKEFILE_LIST))))

ifndef TOASTER_ROOT
$(error TOASTER_ROOT is not set)
endif

export TOASTER_BIN := $(TOASTER_ROOT)/bin
export TOASTER_LIB := $(TOASTER_ROOT)/lib

KQTYPES := Q2_K Q3_K_S Q3_K_M Q3_K_L Q4_K_S Q4_K_M Q5_K_S Q5_K_M Q6_K
IQTYPES := IQ2_XXS IQ2_XS IQ3_XS IQ3_XXS IQ1_S IQ3_S IQ3_M IQ2_S IQ2_M IQ4_XS
IQTYPES += Q2_K_S

QTYPES := Q8_0 $(KQTYPES) $(IQTYPES)

qtype = $(subst .,,$(suffix $(patsubst %.gguf,%,$1)))
ifdef OUTPUT_DIR
qfile = $(patsubst %.imatrix.gguf,%.imatrix,$(foreach m,$1,$(foreach q,$2,$(OUTPUT_DIR)/$m-GGUF/$m.$q.gguf)))
else
qfile = $(patsubst %.imatrix.gguf,%.imatrix,$(foreach m,$1,$(foreach q,$2,$m.$q.gguf)))
endif

ifndef MODELS
MODELS := $(notdir $(patsubst %/,%,$(dir $(wildcard $(SRCDIR)/models/*/config.json))))
endif

qfiles = $(call qfile,$(MODELS),$1)

xinstall = mkdir -p $3 && $1 $2 $3

ifdef INSTALL_DIR
VPATH := $(patsubst %,$(INSTALL_DIR)/%-GGUF,$(MODELS))
install = python $(SRCDIR)/install.py $3 $1 $(INSTALL_DIR)/$2
else
install = true
endif

# xquantize($1=out, $2=type, $3=in[, $4=imat])
xquantize = \
	$(TOASTER_BIN)/quantize --background $(if $4,--imatrix $4) $3 $1 $2

# quantize($1=base, $2=ins, $3=out, $4=install opts)
quantize = \
	$(call xquantize,$3,$(call qtype,$3),$(filter %.gguf,$2),$(filter %.imatrix,$2)) && $(call install,$3,$1-GGUF,$4)

ifdef convert_hf
convert := python $(TOASTER_BIN)/convert-hf-to-gguf.py ${convert_opts}
else
convert := python $(TOASTER_BIN)/convert.py --pad-vocab ${convert_opts}
endif
imatrix := $(TOASTER_BIN)/imatrix -f $(SRCDIR)/data/20k_random_data.txt $(IMATRIX_OPTS)
imatrix_model := python $(SRCDIR)/imatrix_model.py
mkreadme := python $(SRCDIR)/mkreadme.py

ifdef ABORT
$(error Aborted)
endif

f32:: $(call qfiles,F32)
f16:: $(call qfiles,F16)
q8:: $(call qfiles,Q8_0)
imat:: $(call qfiles,imatrix)

kquants iquants:: f16 q8
iquants:: imat
quants:: kquants iquants
all:: quants

kquants:: $(call qfiles,$(KQTYPES))
iquants:: $(call qfiles,$(IQTYPES))

%.F32.gguf:
	$(mkreadme) -o $(@D) -f $(SRCDIR)/models/$(notdir $*)
	$(convert) $(SRCDIR)/models/$(notdir $*) --outtype f32 --outfile $@.tmp && mv $@.tmp $@ && $(call install,$@,$*-GGUF,-k)

%.F16.gguf:
	$(mkreadme) -o $(@D) -f $(SRCDIR)/models/$(notdir $*)
	$(convert) $(SRCDIR)/models/$(notdir $*) --outtype f16 --outfile $@.tmp && mv $@.tmp $@ && $(call install,$@,$*-GGUF,-k)

ifdef LOWMEM
%.imatrix:| %.F16.gguf %.Q8_0.gguf
	$(imatrix) -o $@.tmp -m $(shell $(imatrix_model) $|) && mv $@.tmp $@ && $(call install,$@,$*-GGUF,-k)
else
%.imatrix:| %.F16.gguf
	$(imatrix) -o $@.tmp -m $| && mv $@.tmp $@ && $(call install,$@,$*-GGUF,-k)
endif

.DELETE_ON_ERROR:

%.Q2_K.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q3_K_S.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q3_K_M.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q3_K_L.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q4_K_S.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q4_K_M.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q5_K_S.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q5_K_M.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q6_K.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@)
%.Q8_0.gguf:| %.F16.gguf
	$(call quantize,$*,$|,$@,-k)
%.Q2_K_S.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ2_XXS.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ2_XS.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ3_XS.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ3_XXS.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ1_S.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
# %.IQ4_NL.gguf:| %.F16.gguf %.imatrix
# 	$(call quantize,$*,$|,$@)
%.IQ3_S.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ3_M.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ2_S.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ2_M.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ4_XS.gguf:| %.F16.gguf %.imatrix
	$(call quantize,$*,$|,$@)
